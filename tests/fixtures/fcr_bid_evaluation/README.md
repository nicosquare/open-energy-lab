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
