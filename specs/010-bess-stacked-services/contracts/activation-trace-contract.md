# Regulation Activation Trace Contract

## Ownership And Separation

`open_energy_lab.market.activation` owns source-independent activation import,
normalization, artifact validation, fingerprinting, and loading. The trace is a
separate required simulator input and is never inferred from market price,
capacity, A83 quantity, or A84 price data.

## Schema

The initial schema is `oel.regulation-activation.v1`. It records:

- trace and schema identity
- covered UTC period and half-open convention
- source and canonical resolution
- source name, locator, revision/digest, timezone, and retrieval/creation time
- source value kind and sign meaning
- normalization formula, parameters, clipping, and point-to-interval conversion
- dimensionless interval-average samples
- content and full artifact fingerprints
- license/retention/attribution metadata

## Canonical Sample Meaning

Every sample is the average normalized FCR activation over its own
`[start_utc, end_utc)` interval. Values are finite and within `[-1, 1]`.

- `+1`: full upward response, meaning battery discharge relative to baseline
- `-1`: full downward response, meaning battery charge relative to baseline
- `0`: no FCR deviation from baseline

Replay uses this value as constant interval-average power for energy
integration. It does not interpolate between samples.

## Import Modes

`interval_average` accepts values already carrying explicit interval bounds.

`instantaneous_left_hold` accepts ordered point/setpoint timestamps plus one
declared resolution. Each value applies to the following half-open interval.
The source point semantics and conversion must be recorded; the mode is never
selected from file shape alone.

Any other point-to-interval conversion requires a new semantic version.

## Selected RTE Profile

For the recorded reference day:

```text
source: RTE France grid frequency, 10-second observations
source timezone: Europe/Paris (explicit because raw timestamps are naive)
conversion: instantaneous_left_hold over the following PT10S
activation: clip((50.0 Hz - frequency_hz) / 0.2 Hz, -1, 1)
target sign: positive is upward/discharge
```

The importer processes the selected raw observations directly. It does not
reuse the reference notebook's gap filling or duplicate removal.

## Validation

- Timestamps and intervals must be strictly ordered and unique.
- The declared source timezone must resolve every naive timestamp
  unambiguously; DST folds require explicit resolution.
- Samples must exactly tile the covered period with no gap or overlap.
- All durations must equal the declared resolution.
- Values and normalization inputs must be finite.
- Canonical values must remain within `[-1, 1]` after the declared clipping.
- Content and artifact fingerprints must verify on load.
- The 24-hour reference trace must contain exactly 8,640 PT10S intervals.

## Simulator Compatibility

Before replay, trace start/end must equal the selected replay horizon and every
sample boundary must map exactly to the energy, checkpoint, and FCR grids. A
trace with a different resolution can be accepted only if it has the same FCR
meaning and exact integer grid relationships; no resampling occurs in replay.

## A83/A84 Rule

An ENTSO-E A83/A84 series can satisfy this contract only through an explicit
adapter that proves normalized FCR-command semantics, direction, interval
average meaning, and sufficient temporal resolution. Merely being balancing
data is insufficient. Without that proof it remains supporting market data.

## Failure Diagnostics

Failures identify trace source, period, offending interval or timestamp,
observed value/resolution/sign where applicable, and expected contract.
Specific cases include ambiguous timezone, gap, duplicate, overlap, non-finite
value, out-of-range activation, unknown conversion, incomplete day, grid
misalignment, unsupported schema, and fingerprint mismatch.
