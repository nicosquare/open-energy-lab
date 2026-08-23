# RTE Balancing Energy v5.2 Acquisition Contract

## Ownership

`open_energy_lab.market.rte` owns explicit OAuth, bounded HTTP transport, exact
RTE JSON parsing, source validation, and creation/refresh of one-source
restoration artifacts. It does not construct asset commands, commitments,
dispatch, or settlement.

## Public Operations

```python
fetch_rte_restoration_data(
    request: RestorationMarketDataRequest,
    *,
    client_id: str,
    client_secret: str,
    output_directory: Path,
    auth_transport: RTEAuthTransport | None = None,
    data_transport: RTEDataTransport | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> RestorationFetchResult

refresh_rte_restoration_data(
    current_artifact: RestorationMarketArtifact,
    request: RestorationMarketDataRequest,
    *,
    client_id: str,
    client_secret: str,
    output_directory: Path,
    auth_transport: RTEAuthTransport | None = None,
    data_transport: RTEDataTransport | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> RestorationRefreshResult

load_restoration_market_artifact(path: Path) -> RestorationMarketArtifact
```

Credentials are keyword-only operation arguments. They are absent from request,
result, diagnostic, evidence, filename, cache key, and artifact types. The
offline loader lives in the source-independent artifact module and does not
import `rte`.

## Source Profile

| Item | Value |
|---|---|
| Catalog | RTE Balancing Energy |
| Catalog version | 5.2 |
| API path version | `v5` |
| Token endpoint | `https://digital.iservices.rte-france.com/token/oauth/` |
| aFRR resource | `/open_api/balancing_energy/v5/standard_afrr_data` |
| mFRR resource | `/open_api/balancing_energy/v5/standard_mfrr_data` |
| Method | GET for data; POST for OAuth |
| Data authorization | runtime `Authorization: Bearer …` header |
| Query | `start_date`, `end_date` bounded ISO 8601 values |
| Canonical time | UTC half-open; retain Europe/Paris labels |
| Required resolution | PT15M |

The source endpoint stored in a request is HTTPS origin/path only and may not
contain user information, query, fragment, client identity, or token.

## OAuth Contract

1. Validate the token-free request before reading credentials.
2. Build HTTP Basic authorization from the operation arguments in memory.
3. POST to the token endpoint and accept only the documented success media and
   schema containing a non-empty access token.
4. Keep token response bytes, authorization values, token, and expiry data out
   of evidence, digests, persisted objects, logs, and exception text.
5. Use the bearer token only for the active source operation. Renew in memory
   only when required to complete that operation.
6. Authentication rejection is permanent and receives one attempt.

Injected auth/data transports must be usable by unit tests without network or
real secrets.

## Period Contract

- Both bounds are mandatory, aware, and start before end.
- RTE bounds must align to 15-minute UTC instants.
- The requested interval must satisfy the documented source lookback and
  maximum-window rules. The adapter may split a larger caller period into
  deterministic contiguous source-supported windows, but publication remains
  atomic for the caller's whole request.
- The response root and each row must cover the requested period exactly after
  declared timezone normalization. Partial coverage fails.
- A local DST gap/fold does not alter continuous UTC coverage; local offset and
  fold identity remain recorded.

## aFRR JSON Contract

Expected root: `picasso` with `start_date`, `end_date`, `resolution`, and
`picasso_mesures`. Required row fields:

```text
start_date
end_date
upward_afrr_requested_need
downward_afrr_requested_need
upward_afrr_activated_volume_for_fr
downward_afrr_activated_volume_for_fr
upward_afrr_activated_volume_in_fr
downward_afrr_activated_volume_in_fr
upward_weighted_average_price_afrr_activated_for_fr
downward_weighted_average_price_afrr_activated_for_fr
```

Requested need, activated for France, activated in France, and weighted-average
price become separate series. Direction and units are explicit. Row order may
be source-descending; normalization orders by interval while preserving the
source row index. Duplicate/conflicting intervals, unknown resolution/unit,
malformed numbers, incomplete coverage, and unexpected direction fail.

The verified reference request
`[2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)` must yield exactly four
consecutive PT15M rows. That count is a selected-profile gate, not a rule that
all requests contain four rows.

## mFRR JSON Contract

Expected root: `mari` with `start_date`, `end_date`, `resolution`, and
`mari_mesures`. Each row retains:

```text
start_date, end_date, direction
total_requested_volume_SA, total_satisfied_need_SA, total_activated_volume_SA
total_requested_volume_DA, total_satisfied_need_DA, total_activated_volume_DA
clearing_price, settlement_price_current, settlement_price_previous
requested_activated_volumes_by_prices
total_volume_submitted_offers, total_volume_filtered_offers
```

Nested requested-volume-by-price entries retain activation type, requested
price meaning, requested volume, and satisfied need. Directional rows for the
same interval remain distinct. SA and DA remain distinct. A field that is
missing, JSON null, or numeric zero maps to a different value state.

The reference request
`[2026-08-15T10:15:00Z, 2026-08-15T10:30:00Z)` must retain both directional
rows and the downward SA requested/satisfied observations. Null DA values are
valid sparse-source evidence; they do not create an event.

## Transport and Retry Contract

- Bound response bytes before parsing; reject oversized bodies atomically.
- Validate status, media type, JSON syntax, root, and schema.
- Retry only timeout, connection interruption, HTTP 408, 429, and transient 5xx.
- Make at most three total attempts per failed source window, including the
  initial call.
- Honor a valid non-negative `Retry-After` subject to the documented safe cap;
  otherwise use the deterministic adapter backoff.
- Treat authentication and other permanent 4xx responses as one-attempt
  failures.
- Diagnostics contain source, resource, sanitized field/window condition,
  expected contract, final category, and attempt count. They contain no header,
  token, client value, raw body, or credential-bearing URL.

## Atomicity and Refresh

All required windows and series are parsed and validated in memory before a
manifest is published. On any error, no complete artifact appears.

Refresh first verifies the current artifact and matching request identity. If
the normalized `content_fingerprint` is unchanged, return `UNCHANGED` and write
nothing. If changed, create one successor with the prior
`artifact_fingerprint`; never overwrite. Failure preserves the current file.

## Credential Sentinel Matrix

Tests inject unique client-ID, client-secret, basic-header, access-token, and
bearer-header sentinels and assert zero matches across:

- request/result repr and exceptions
- stdout/stderr and captured logs
- filenames, output paths, cache identities, and temporary-file names
- artifact/fixture bytes and fingerprints' input payloads
- notebook source, output, plot labels, and saved notebook state

## Reference Evidence

The planning digests are verification evidence only:

- aFRR response bytes:
  `d2496d713c7f217ff76487db2aba0b7a49479861118bea61ca3c001fbbfe2eb3`
- mFRR response bytes:
  `ce9d3c3d694a78776e5bdb188239f9b2ed4b711e3c389d0e89c8a47e5391d1a1`

Fixture staging records a fresh retrieval timestamp, raw digest, transformation
history, content fingerprint, artifact fingerprint, and restricted policy.
