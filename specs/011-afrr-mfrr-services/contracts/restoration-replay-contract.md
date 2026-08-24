# aFRR and mFRR Replay Contract

## Ownership

Control owns fixed directional commitments and accepted no-lookahead energy
baselines. The simulator owns capability enforcement, battery physics,
requested versus delivered attribution, non-performance, energy aggregation,
throughput, and result fingerprints. Settlement consumes replay results but
never changes dispatch.

Feature 010 replay types, calculations, fingerprints, and fixtures remain
unchanged.

## Public Interfaces

```python
build_afrr_baseline(config: AFRRBaselineConfig) -> RestorationBaselineBundle
build_mfrr_baseline(config: MFRRBaselineConfig) -> RestorationBaselineBundle

replay_afrr(request: AFRRReplayRequest) -> AFRRReplayResult
replay_mfrr(request: MFRRReplayRequest) -> MFRRReplayResult
```

The two replay functions require exact activation and commitment types. There
is no public generic function that guesses a product from fields.

## Baseline and Commitment Validation

For battery discharge limit `D`, charge limit `C`, upward commitment `U`, and
downward commitment `L`, every accepted energy baseline value must satisfy:

```text
-D + U <= baseline_kw <= C - L
```

Validation also covers:

- matching product identity and complete temporal alignment
- non-negative directional commitments and explicit eligibility
- battery power, min/max/initial SOC, capacity, and efficiencies
- usable upward/downward energy headroom for declared duration assumptions
- service ramp, activation-time, and duration capability
- finite positive tolerance and replay step

Baseline builders receive no activation input. They may prove static declared
headroom but cannot claim feasibility against future activation.

## Replay Selection Gate

One request contains:

- one battery and initial state
- one restoration capability
- one accepted energy baseline
- one matching directional capacity schedule
- exactly one `AFRRActivationTrajectory` or one `MFRRActivationSequence`
- one integration grid and tolerance
- all input fingerprints

FCR, simultaneous aFRR/mFRR, mismatched commitments, or wrong exact runtime
types fail before any battery step.

## Dispatch Equation

At each integration interval:

```text
requested_combined_kw = accepted_baseline_kw + requested_balancing_kw
```

The restoration layer applies commitment, directional headroom, ramp,
activation-time, and duration capability deterministically. The resulting
capability-accepted combined request is passed to Feature 010's unchanged
`apply_power_request`, which enforces charge/discharge power, SOC, efficiency,
and step duration.

Delivery attribution is baseline-relative:

```text
delivered_balancing_kw = delivered_combined_kw - accepted_baseline_kw
tracking_error_kw = requested_balancing_kw - delivered_balancing_kw
```

Requested, capability-accepted, and physically delivered values remain
separately visible. The battery never violates configured power or SOC bounds.

## aFRR Replay

- Consume interval-average signed-kW samples directly; never interpolate or
  upsample them.
- For the real PT15M trajectory, the replay integration grid is PT15M.
- High-resolution synthetic trajectories use their native grid for ramp and
  response validation.
- Report each interval's directional request/delivery, signed and absolute
  tracking error, delivered/undelivered energy, response delay, achieved ramp,
  SOC, energy, power/energy headroom, cause, and cause duration.
- Aggregate by direction and whole horizon with exact energy conservation.

## mFRR Replay

- Expand each event's analytic delay/ramp/hold/ramp profile only onto a grid
  whose boundaries conserve all segment energy. Unsupported partial boundaries
  fail rather than silently prorate.
- Record requested and actual start/completion, SA/DA identity, direction,
  requested/delivered/undelivered event energy, achieved ramp, delay, and
  non-performance causes.
- Keep per-event and aggregate SA, DA, upward, and downward results separate.
- Reject overlapping events before expansion or replay.

## Non-Performance Causes

Every non-zero shortfall receives deterministic ordered causes chosen from:

```text
commitment_limit
upward_headroom
downward_headroom
ramp_limit
activation_time_limit
duration_limit
charge_power_limit
discharge_power_limit
minimum_soc
maximum_soc
energy_headroom
```

Input-invalid cases such as wrong product, gaps, overlap, and incomplete event
coverage are validation failures, not physical saturation causes.

## Zero Activation

With all aFRR samples zero or an empty valid mFRR event sequence:

- requested combined power equals the accepted baseline at every interval
- delivered balancing energy is exactly zero
- non-performance is exactly zero
- physical baseline/SOC behavior matches the same baseline-only replay within
  `1e-6`
- balancing-energy revenue is zero when settlement is available
- capacity eligibility remains governed by its explicit rule

## Energy, Throughput, and Multi-rate Conservation

For every sample/event and aggregate, preserve charge, discharge, net,
requested activation, delivered activation, and undelivered activation energy.
Battery-terminal throughput is absolute delivered charge plus absolute
delivered discharge energy. No sample or event portion may be dropped,
duplicated, or silently prorated.

## Result Contracts

Both products expose immutable chronological samples, physical totals, SOC and
headroom, ordered diagnostics, input fingerprints, semantics version, and
result fingerprint.

`AFRRReplayResult` adds tracking-oriented interval/directional summaries.
`MFRRReplayResult` adds typed `MFRREventPerformance` records. Irrelevant fields
for the other product do not appear as zero/null placeholders.

## Determinism

Repeated replay with identical semantic inputs produces identical sample/event
ordering, floating values within canonical normalization, diagnostics,
aggregates, and fingerprints. Replay has no network, credential, environment,
clock, randomness, solver, or notebook dependency.

## Manual Validation Cases

aFRR oracles cover upward, downward, zero, alternating direction, ramp-limited,
power-limited, SOC-limited, and headroom-limited segments.

mFRR oracles cover upward SA, downward DA, zero-delay and delayed events,
non-zero linear ramps, full hold, energy integral, timing failure, duration
failure, physical saturation, and overlap rejection.

Every published expected intermediate and total uses absolute tolerance
`1e-6`.

## Compatibility Gate

The full Feature 010 market/control/simulator unit and integration suites run
unchanged. Existing FCR public symbols, accepted/rejected input types,
fingerprints, fixture bytes, and reference results must be byte-stable.
