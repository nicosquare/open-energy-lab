# Canonical Market Artifact Contract

## Ownership And Purpose

`open_energy_lab.market.artifact` owns the immutable source-independent market
artifact, validation, fingerprinting, optional sidecar integrity, load, and
atomic write behavior. Simulator, controller, optimizer, notebook, and dataset
consumers see this contract only; they do not see ENTSO-E parameters or XML.

## Schema

The initial schema identifier is `oel.market-data.v1`. A valid artifact has:

- one France profile and area `10YFR-RTE------C`
- exact requested and actual covered UTC periods
- Europe/Paris delivery metadata and interval convention
- exactly one complete `day_ahead_price` series
- exactly one complete `fcr_contracted_volume` series
- exactly one complete `fcr_capacity_price` series
- source response digests and retention/license metadata
- selected/superseded source document identities and revisions
- sanitized source query windows
- normalization version, content fingerprint, artifact fingerprint, and lineage

Unknown schema versions fail before any consumer can use values.

## Required Series Contract

| Series | Canonical unit | Reference canonical resolution | Value rules |
| --- | --- | --- | --- |
| `day_ahead_price` | EUR/MWh | PT1H | Finite; negative allowed |
| `fcr_contracted_volume` | MW | PT4H | Finite and non-negative |
| `fcr_capacity_price` | EUR/MW/h | PT4H | Finite and source-profile compatible |

Every observation has an unambiguous canonical interval, exact source-value
field, and selected source document reference. Intervals within a series are
strictly ordered, unique, non-overlapping, and gap-free across the declared
covered period. Both FCR series have identical PT4H intervals and reference
the same selected combined A81 document and product identity.

## Time Contract

UTC boundaries are authoritative for ordering and calculation. Each boundary
also records a Europe/Paris local label, UTC offset, and fold. Load validation
recomputes local metadata and fails on mismatch, impossible local time, or an
ambiguous repeated time without fold evidence. A 23- or 25-hour local day is
valid market data when its UTC intervals are complete; replay eligibility is a
separate contract.

## Raw Evidence Contract

- Every raw response is represented by byte count, media type, SHA-256,
  retrieval time, sanitized request identity, and retention basis.
- Raw bytes are never embedded in canonical JSON.
- `digest_only` is always valid when normalized-fixture reuse is permitted.
- `sidecar_retained` additionally requires a safe relative locator and digest.
- Loading resolves sidecars beneath an explicit artifact root, rejects absolute
  paths and traversal, and verifies bytes before returning the artifact.
- A missing or mismatched optional sidecar invalidates an artifact that claims
  it is retained.

## Fingerprints

`content_fingerprint` hashes canonical semantic content and selected source
revisions but excludes retrieval/publication time, artifact ID, lineage, and
sidecar locator. It is used only for change comparison.

`artifact_fingerprint` hashes the full deterministic manifest except its own
field. It is verified on load and identifies replay input.

Lists have defined order, keys are sorted for hashing, text is UTF-8, and JSON
serialization rejects NaN/infinity. Consumers never recompute fingerprints
from a lossy dataframe representation.

## Immutability And Filenames

Artifact paths are derived from token-free artifact identity/fingerprint and
never overwrite an existing different manifest. Refresh publishes a new file
and stores the predecessor fingerprint. An identical existing artifact may be
reused only after full byte/fingerprint validation.

## Load Operation

```python
load_market_data_artifact(
    path: Path,
    *,
    artifact_root: Path | None = None,
) -> MarketDataArtifact
```

Loading performs schema, integrity, sidecar, interval, area, series, unit,
source-evidence, and cross-series validation. It never imports or invokes an
ENTSO-E transport and never reads an environment token.

## Source Independence

Series retain `source_name` and document provenance for audit, but the
simulator matches canonical series IDs, units, intervals, and semantic versions
only. A future source can implement the same contract, but it cannot be labeled
as satisfying the required ENTSO-E demonstration unless its series provenance
actually does so.

## Minimum Failure Matrix

Load must fail specifically for unknown version, malformed JSON, missing
required field/series, non-finite value, fingerprint mismatch, unsafe/missing/
mismatched sidecar, token sentinel in forbidden metadata, wrong France area,
gap, overlap, conflicting duplicate, UTC/local mismatch, unit/resolution
mismatch, split/legacy A89 FCR provenance, or incomplete requested coverage.
