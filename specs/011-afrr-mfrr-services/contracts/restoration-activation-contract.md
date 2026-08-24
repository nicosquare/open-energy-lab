# Restoration Activation and Derived Scenario Contract

## Product Boundary

Feature 011 exposes two source-independent, non-interchangeable activation
inputs:

- `AFRRActivationTrajectory`: complete signed-kW interval-average automatic
  request samples
- `MFRRActivationSequence`: typed scheduled/direct manual events

Neither accepts or converts Feature 010's dimensionless
`RegulationActivationTrace`. Exact runtime type and product checks occur before
mapping, replay, or settlement.

## Derived Simulation Mapping

Area-level data may produce a simulation input only through a persisted mapping
with exact source artifact/series fingerprints, product/direction, one fixed
allocation fraction, MW-to-kW scale, commitment fingerprint, assumptions,
creation time, and output label `derived_simulation`.

For every driver observation:

```text
requested_bess_kw = area_requested_mw * 1000 * allocation_fraction
```

Rules:

- fraction is finite and in `[0,1]`
- one scenario uses one fraction throughout
- no period-relative normalization, interpolation, upsampling, or clipping
- each mapped magnitude must fit the matching directional commitment
- requested need/volume drives the result; activated, satisfied, and price
  fields are comparison/context only
- the mapping fingerprint appears on trajectory/events, replay, plots, tables,
  and settlement metadata

## aFRR Trajectory Contract

Each sample is the signed requested BESS balancing power averaged over its
half-open interval:

- negative: upward response/discharge
- positive: downward response/charge
- zero: no aFRR activation

The trajectory declares product `AFRR`, period, fixed resolution, sign and
sample semantics, source/derivation kind, an explicit
`created_or_retrieved_at_utc` provenance timestamp, and fingerprint. The
timestamp participates in trajectory identity. Samples must be chronological,
non-overlapping, gap-free, and cover the replay horizon exactly. Energy
integrates directly as
`power_kw * interval_hours`.

No point/setpoint data satisfies this contract without a separately provenanced
conversion. No operation interpolates or upsamples a trajectory.

### RTE-derived aFRR rule

Upward requested need maps to negative power; downward requested need maps to
positive power. If both source values are greater than zero in one interval,
the interval and entire derived trajectory fail as ambiguous. Netting,
direction selection, and invented subinterval ordering are prohibited.

The reference fraction `0.001` maps the four verified PT15M upward requested
need observations chronologically to `[-425, -315, -290, -345]` kW. These are
simulated interval-average BESS requests, not observed automatic control.

## mFRR Event Contract

Every event has product `MFRR`, exact kind `SCHEDULED` or `DIRECT`, explicit
direction, requested start, non-negative delay/ramp-up/hold/ramp-down durations,
non-negative requested magnitude kW, source/derivation, and fingerprint.

The signed request profile is:

1. zero during activation delay
2. linear zero-to-magnitude ramp-up
3. constant magnitude during hold
4. linear magnitude-to-zero ramp-down

Upward applies negative sign and downward positive sign. Total duration must be
positive. Requested event energy magnitude is:

```text
power_kw * (hold_seconds + 0.5*ramp_up_seconds + 0.5*ramp_down_seconds) / 3600
```

Requested energy is derived only and cannot be supplied as a competing input.

### Event sequence validation

- Event IDs and fingerprints are unique.
- Complete half-open event intervals include delay and all power segments.
- Every complete event lies within the replay horizon.
- Events order deterministically by requested start then ID.
- Any overlap is rejected before replay, irrespective of direction or SA/DA.
- No addition, netting, truncation, or precedence rule exists in v1.

### RTE-derived mFRR rule

Only the matching SA requested-volume field may drive the reference SA event.
Satisfied need and locally activated volume remain comparison observations.
Missing/null DA fields produce no event.

The reference event uses the verified downward SA record and fraction `0.001`:

```text
start:       2026-08-15T10:15:00Z
kind:        SCHEDULED
direction:   DOWNWARD
delay:       0 seconds
ramp-up:     0 seconds
hold:        900 seconds
ramp-down:   0 seconds
power:       357 kW
energy:      89.25 kWh
```

The rectangular event shape is an explicit derived-scenario assumption for the
15-minute area record, not an observed RTE-to-asset activation order. Synthetic
fixtures prove non-zero delay, ramp, both directions, and direct activation.

## Capacity Rejection

Mapping requires the exact compatible commitment schedule. Each aFRR sample or
mFRR event magnitude is checked against the commitment covering its full
interval and direction. A failure names source series, source interval,
calculated kW, allocation fraction, commitment kW, product, and direction.

Mapping never shrinks or clips a request to make it feasible.

## Fingerprint Inputs

Activation fingerprints include:

- schema and product-semantics versions
- source/derivation kind and all source fingerprints
- fixed allocation mapping when derived
- period/grid and every sample or event field
- sign, interval-average, and piecewise-shape semantics
- deterministic ordering

Creation/retrieval provenance is included in the full artifact identity. No
credential, output path, or runtime object is included.

## Required Failure Matrix

Validation covers wrong product/type, invalid direction, missing lineage,
non-finite values, fraction outside bounds, capacity excess, aFRR opposing need,
gaps, overlaps, wrong resolution, point/setpoint ambiguity, mFRR unknown kind,
missing start, negative durations, zero total duration, event outside horizon,
event overlap, requested-energy input, and sparse DA fabrication.
