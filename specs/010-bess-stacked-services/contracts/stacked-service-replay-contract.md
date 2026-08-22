# Stacked-Service Replay Contract

## Ownership

`open_energy_lab.simulator.stacked_service` owns schedule validation, multi-rate
alignment, battery-constrained physical replay, tracking, saturation, and
result traces. It accepts canonical artifacts and fixed schedules only. It does
not fetch data or choose bids.

`open_energy_lab.control.stacked_service` owns deterministic comparison schedule
construction. It does not simulate physics, settle revenue, or access a
network.

## Inputs

- One valid `MarketDataArtifact`
- One valid `RegulationActivationTrace`
- One existing `BatteryComponent`
- One fixed hourly `EnergyBaselineSchedule` in charge-positive kW
- One fixed non-negative four-hour `FCRCapacitySchedule` in kW
- One exact `MultiRateTimeContract`
- Optional explicit `FCRPenaltyRule`
- Optional report-only terminal SOC target
- Positive numeric tolerance, default `1e-6`
- Simulation-semantics version

## Pre-Replay Validation

The replay horizon must:

- be contained in both artifacts
- equal the activation trace period
- start/end on complete hourly and FCR product boundaries
- have no partial leading or trailing energy/FCR block
- map every PT10S sample to exactly one PT1H energy interval, one PT15M
  checkpoint interval, and one PT4H FCR block
- contain complete aligned market price, reserve volume, and reserve price
  observations

For every aligned baseline/commitment pair:

```text
baseline_kw - reserve_kw >= -battery.max_discharge_kw
baseline_kw + reserve_kw <=  battery.max_charge_kw
reserve_kw / 1000 <= market_fcr_volume_mw
```

Failure prevents a normal replay. A separately named diagnostic replay may
execute an intentionally invalid schedule to expose saturation, but its result
must be marked `commitment_validation_failed` and cannot be represented as a
valid commitment.

## Dispatch Equation

For each activation interval:

```text
requested_fcr_kw = -activation * reserve_kw
requested_combined_kw = baseline_kw + requested_fcr_kw
```

Positive combined power charges the battery. The request is applied through
the existing `apply_power_request` function for the exact activation duration.
Delivered power and SOC always respect battery charge/discharge power,
minimum/maximum SOC, and direction-specific efficiency.

## Delivery Attribution

When `reserve_kw > 0`:

```text
delivered_fcr_kw = delivered_combined_kw - baseline_kw
tracking_error_kw = requested_fcr_kw - delivered_fcr_kw
non_delivery_energy_kwh = abs(tracking_error_kw) * duration_h
```

When `reserve_kw == 0`:

```text
requested_fcr_kw = 0
delivered_fcr_kw = 0
tracking_error_kw = 0
non_delivery_energy_kwh = 0
baseline_delivery_error_kw = baseline_kw - delivered_combined_kw
```

Baseline delivery error never creates an FCR penalty in the zero-FCR case.

## Saturation Causes

Each sample reports an ordered set drawn from:

1. `charge_power_limit`
2. `discharge_power_limit`
3. `minimum_soc_limit`
4. `maximum_soc_limit`

Both a power and SOC cause may appear if both bind. Contiguous samples are
aggregated into deterministic chronological `SaturationEvent` records.

## Energy And Checkpoints

- Battery physics advances only at activation resolution.
- Charge/discharge terminal energy is derived from delivered power and interval
  duration.
- SOC stored-energy changes reuse existing efficiency semantics.
- PT15M, PT1H, and PT4H summaries aggregate the same substeps; direct and
  aggregated energy must reconcile within `1e-6 kWh` per period and horizon.
- State checkpoints include the initial state and every checkpoint boundary.

## Required Result Fields

Every replay returns ordered per-sample values for baseline, reserve,
activation, requested/delivered FCR, requested/delivered combined power,
baseline diagnostic, tracking, non-delivery, charge/discharge energy, SOC, and
saturation causes. It also returns checkpoint summaries, events, tracking
aggregates, throughput, settlement, optional terminal-target report, input
fingerprints, trace fingerprint, and result fingerprint.

## Determinism

No random generator, wall clock, environment state, token, or transport is
available to replay. Identical validated inputs must produce byte-identical
ordered trace fingerprints, event ordering, aggregates, and settlement totals.

## Deterministic Schedule Builders

### Regulation-only

- Energy baseline is zero in every interval.
- FCR schedule is caller-fixed.
- Initial stored energy is efficiency-aware centered energy.
- No recovery/recentering power is added.
- Activation values are not read during schedule construction.

### Stacked heuristic

- Invoke the existing deterministic price-threshold request for each energy
  interval.
- Clip it to
  `[-max_discharge_kw + reserve_kw, max_charge_kw - reserve_kw]`.
- Reject an empty admissible interval.
- Future activation is not an input.
- Output is a fixed schedule and makes no robust SOC guarantee.

## Compatibility Gates

- With zero FCR and identical battery, schedule, grid, price, and existing
  settlement configuration, physical power, SOC, throughput, and settlement
  match the current arbitrage behavior within `1e-6`.
- With zero energy baseline and nonzero valid FCR, day-ahead revenue is exactly
  zero while FCR delivery, capacity revenue, tracking, throughput, and penalty
  remain observable.
- Adding/removing a terminal SOC target changes only the terminal report.
