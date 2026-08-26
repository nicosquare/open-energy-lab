# FCR Bid-Evaluation Fixtures

This directory contains the small, reviewable evidence used by Feature 012.
Routine tests must remain deterministic and offline: they do not initialize the
reference submodule, start Julia or Gurobi, access the network, or read the full
regulation dataset.

## Fixture Classes

### Authored oracle

`manual_fcr_bid_evaluation_v1.json` is a hand-calculable fixture authored for
Open Energy Lab. It may contain every input and expected intermediate needed to
verify sign conversion, battery physics, delivery attribution, settlement,
diagnostics, and fingerprints. Its expected values must be calculated
independently of the evaluator under test.

### Golden reference fixture

`robust_storage_bidding_2023-06-18_aggregate_v1.json` is a normalized,
provenance-rich manifest derived from the pinned reference implementation. It
contains fixed decisions, prices, configuration, mappings, supported aggregate
evidence, precision bounds, and an external-data descriptor. It is not a copy
of the original result or regulation signal.

Reference-result claims are limited to fields supported by the generated JSON.
Detailed ten-second state, tracking, non-delivery, saturation, directional FCR
energy, separate observed FCR subrevenues, and Open Energy Lab throughput remain
unavailable as reference evidence.

## External-Only Activation Data

The reference regulation CSV is approximately 529 MB and is never committed,
packaged, uploaded as a CI artifact, or read by routine tests. An authorized
researcher downloads the bytes named by the pinned reference README and places
them at:

```text
artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

The repository-wide `artifacts/` ignore rule governs this location. The public
loader nevertheless requires an explicit caller-supplied path; it does not
search this directory, inspect environment variables, download the file, or
fall back to `baselines/robust_storage_bidding/`.

The accepted descriptor is:

```text
URL: https://github.com/lauinger/robust-storage-bidding/releases/download/v0.1/regulation_signal.csv
size: 528805941 bytes
SHA-256: 0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13
header: DateTime,Frequency (Hz),xi,xi_EU
selected date/column: 2023-06-18 / xi_EU
selected cadence/count: PT10S / 8640 rows
```

Tests that need those bytes are marked `external_reference_data` and must be
selected explicitly. Only the optional test wrapper may skip when the file is
absent; the public loader fails with installation and integrity guidance.

## Refresh Boundary

Normal evaluation never writes fixtures. Reference execution and fixture
refresh are explicit researcher operations. Normalized output is written below
ignored `artifacts/` first, semantically compared with the committed fixture,
and promoted only through review. The refresh helper must not execute Julia,
Gurobi, or mutate `baselines/`.

## Initial Full-Data Acceptance Record

On 2026-08-26, the complete consumer was run with the digest-matched local CSV
explicitly supplied from the researcher's existing checkout. This was an
explicit path argument, not a production fallback or routine-test dependency.
It produced 24 hourly decisions, six FCR blocks, 96 checkpoints, and 8,640 PT10S
activation samples with no saturation events. The overall comparison was
`source_precision_compatible` and no supported field was a mismatch.

Exact supported fields were objective, objective bound, total profit, combined
FCR profit, initial stored energy, charge energy, and both mapped power extrema.
Day-ahead profit, minimum/maximum/terminal stored energy, and discharge energy
were `source_precision_compatible`. Reference intraday detail, solve/runtime
metadata comparisons, and unsupported per-step evidence remained explicitly
`unavailable`.

Stable content/results from that acceptance run were:

```text
fixture:    6bce7f00bb38b257a6f5e4186a8b8dab06d7f5f41336238b499b153b3f7a59fd
mapping:    53f1819fe433e55e87aa98f19f280dbdfabdef935658abd531bbe079fec88945
plan:       6bbbf946b8d12762971e5b369d4f63fa57b0a17d8977ca84de4655927bf36f11
trace:      f292f4990d99f6ca4aa7bb12c304b70751396e3c2005544577c58ceb153573f6
settlement: 8e5382463fd8e9bd110214fa4cd87be7539ae0fab70eb4ead0bb2b55cbbf72ca
comparison: 1e16c8f03f3c8c649ab1a435d8a14849f51b168b91fc7915df236c492a8b274e
```

The settlement fingerprint was revalidated after the Feature 012 audit schema
added directional FCR energy and explicit combined-FCR reconciliation. That
additive report change left the physical trace and comparison fingerprint
unchanged.

The activation artifact, evaluation-input, and final result fingerprints also
bind the caller-supplied locator. They are intentionally not promoted as
location-independent golden values; placing identical bytes at the supported
`artifacts/` path changes lineage while leaving the physical, settlement, and
comparison fingerprints above unchanged.
