# Research: FCR Bid-Evaluation Parity

**Feature**: `012-fcr-bid-evaluation-parity`
**Date**: 2026-08-26
**Pinned reference commit**: `7e44738bb30e5c8204efe40103b9be4c2203685c`

## Decision 1: Add a bidder-neutral envelope around existing schedules

**Decision**: Add an immutable fixed-plan envelope under
`open_energy_lab.control` that references exactly one existing
`EnergyBaselineSchedule` and one existing `FCRCapacitySchedule`. Put evaluation,
daily reporting, and comparison under `open_energy_lab.simulator`.

**Rationale**: Feature 010 already has the correct ownership split:
`control/stacked_service.py` constructs schedules,
`simulator/stacked_service.py` validates and replays them, and
`simulator/fcr_settlement.py` accounts for them. A plan is a controller/bidder
output; physical validity and realized performance remain simulator concerns.
`BaselineScheduleBundle` is not a suitable plan because it contains heuristic
recovery concerns and lacks producer, cutoff, objective, bound, and diagnostic
metadata.

**Alternatives considered**:

- Copy schedule interval values into a new bid type: rejected because it creates
  two authoritative schedule representations and permits drift.
- Put plans in `planning`: rejected because fixed manual and heuristic plans must
  not acquire an optimization dependency or planning meaning.
- Add bidder fields directly to Feature 010 schedules: rejected because it would
  change their fingerprints and conflate bid provenance with physical content.

## Decision 2: Use one physical kernel without inventing market provenance

**Decision**: Factor the current private physical replay logic in
`src/open_energy_lab/simulator/stacked_service.py` into one source-independent
kernel. The existing `StackedServiceReplayRequest` and `replay_stacked_services`
remain the Feature 010 adapter and must produce byte-identical public outputs and
fingerprints. The new evaluator supplies the same schedules, activation trace,
battery, and time types through an additive reference-context adapter.

**Rationale**: Feature 010's `MarketDataArtifact` is intentionally a closed
France A44/combined-A81 acquisition artifact and its request validates FCR bids
against an observed contracted-volume series. The pinned reference JSON contains
day-ahead prices, FCR prices, and accepted fixed decisions, but no A81 contracted
volume observation. Fabricating an A81 artifact or relabelling the battery limit
as observed market volume would violate provenance requirements. Sharing the
private kernel preserves one battery simulator while allowing a truthful,
source-independent reference input view.

**Alternatives considered**:

- Create a synthetic A44/A81 `MarketDataArtifact`: rejected as false source
  evidence.
- Bypass the existing battery transition with a reference-specific simulator:
  rejected because results would no longer use a common environment.
- Widen Feature 010's artifact schema or accepted types in place: rejected
  because Feature 010's rejection behavior, artifact bytes, and fingerprints are
  closed compatibility contracts.

## Decision 3: Separate producer-visible lineage from evaluation binding

**Decision**: The plan fingerprint covers the schedules, producer, semantics,
information cutoff, producer-visible input lineage, solve state, objective/bound
metadata, and ordered diagnostics. Activation, realized prices not available by
the cutoff, evaluation profile, and result expectations are bound only in the
evaluation request and evaluation fingerprint.

**Rationale**: Requiring a future activation fingerprint in a bidder-produced
object would encode look-ahead. The daily report can still aggregate plan and
evaluation fingerprints into complete lineage without implying that the bidder
saw the activation trace.

**Alternatives considered**:

- Require activation identity in every plan: rejected because it weakens the
  information-cutoff guarantee.
- Omit activation identity from all outputs: rejected because evaluation results
  would not be reproducible.

## Decision 4: Map power, activation, and time explicitly

**Decision**: Use these reference-to-library mappings:

```text
library_baseline_kw = -reference_x0_kw
library_fcr_capacity_kw = reference_xr_kw
library_activation = reference_xi_EU
library_requested_fcr_kw = -library_activation * library_fcr_capacity_kw
library_requested_combined_kw = library_baseline_kw + library_requested_fcr_kw
```

This yields `library_requested_combined_kw = -reference_requested_power_kw`.
Reference power extrema therefore compare with reversed signs and bounds:

```text
reference_min_power_kw = -library_max_combined_power_kw
reference_max_power_kw = -library_min_combined_power_kw
```

The ordinary-day mapping has 360 PT10S samples per hourly `x0`, 90 PT10S
samples per PT15M checkpoint, and 1,440 PT10S samples per four-hour `xr`.
Reference naive labels are declared as the Europe/Paris delivery day
`2023-06-18T00:00:00+02:00` to `2023-06-19T00:00:00+02:00`, canonicalized to
UTC `[2023-06-17T22:00:00Z, 2023-06-18T22:00:00Z)`.

**Rationale**: The reference declares positive power as battery outflow in
`baselines/robust_storage_bidding/code/01_datastruct.jl` and computes
`x_soll = x0 + xi*xr + xa` in
`baselines/robust_storage_bidding/code/03_backtest_save.jl`. Feature 010 uses
charge-positive battery power and computes requested FCR as `-activation *
capacity`. France price files and the reference's naive day selection represent a
local market-delivery day. Explicit Europe/Paris conversion preserves that
meaning while keeping OEL computation UTC-authoritative.

**Alternatives considered**:

- Negate `xi_EU` instead of `x0`: rejected because it would reverse activation
  direction relative to the existing replay equation.
- Treat naive labels as UTC: rejected because it would mislabel the French
  delivery day, although aggregate arithmetic would happen to be unchanged.
- Support 23/25-hour parity days immediately: rejected because the reference
  experiment and fixed counts assume an ordinary 24-hour day.

## Decision 5: Preserve the shared battery equation in its supported domain

**Decision**: Represent the reference battery as 100 kWh capacity, 50 kW charge
and discharge limits, min/max SOC fractions 0.1/0.9, initial SOC fraction
0.53328, and charge/discharge efficiencies 0.92. Compare stored energy in kWh;
normalized SOC is supplementary only.

**Rationale**: The reference evolves stored energy as

```text
y_next = y + dt * min(-eta_c * x, -x / eta_d)
```

for discharge-positive `x`. After sign inversion this is the same efficiency
equation implemented by Feature 010's charge-positive `apply_power_request`.
The selected case remains inside 10--90 kWh and -50--50 kW, so the different
out-of-domain treatment is not exercised.

**Alternatives considered**:

- Treat reference `soc_*` as normalized fractions: rejected; the source defines
  and reports them in kWh.
- Reimplement the Julia update: rejected; the existing battery transition is the
  behavior later bidders must share.

## Decision 6: Add an explicit reference settlement profile

**Decision**: Leave `settle_stacked_services()` and `SettlementBreakdown`
unchanged. Add an opt-in profile that reports:

```text
day_ahead_revenue = -sum(baseline_kw * hours * price_EUR_per_MWh / 1000)
capacity_revenue = sum(capacity_kw * block_price_EUR_per_kW_per_block)
activation_revenue = -sum(delivered_fcr_kw * dt * price_EUR_per_kWh)
total_profit = day_ahead + capacity + activation - penalty
```

Reference `p0` is EUR/kWh (loaded from EUR/MWh and divided by 1,000).
Reference `pr` is EUR/kW per four-hour block (loaded from EUR/MW/4h and divided
by 1,000). A Feature 010-style hourly capacity price is therefore
`pr * 1000 / 4` EUR/MW/h.

**Rationale**: The formulas follow
`baselines/robust_storage_bidding/code/02_model.jl` price loading and
`code/03_backtest_save.jl` realized accounting. Delivered FCR energy is the
clarified library rule: unavailable service is unpaid and can be penalized
separately. For the selected no-curtailment case it equals requested activation
accounting and capacity plus activation reconciles with `profit_fcr`.

**Alternatives considered**:

- Change Feature 010's default activation status from `not_modeled`: rejected
  because it would alter old results and fingerprints.
- Price requested activation after saturation: rejected because it pays
  unavailable service and conflicts with the clarified requirement.
- Treat `psoc` as a realized non-delivery penalty: rejected; it is an optimizer
  slack penalty, not part of `bt_simulation` realized profit.

## Decision 7: Define the bounded parity domain explicitly

**Decision**: Initial reference-result parity applies only when fixed `x0`/`xr`,
prices, activation, battery parameters, and ordinary-day alignment are declared;
reference combined power remains within its power limits; stored energy remains
inside 10--90 kWh; intraday adjustment `xa` is zero; and compared fields exist in
the generated JSON.

**Rationale**: Reference total profit prices clipped combined power while
reference `profit_fcr` prices requested `xi*xr`, which diverges under
curtailment. The reference also does not clamp stored energy to its bounds during
backtest. The 2023-06-18 result does not exercise either difference, so bounded
parity is sound without migrating those brittle behaviors.

**Alternatives considered**:

- Claim parity under saturation or SOC violation: rejected because the source
  and OEL intentionally differ there.
- Copy the reference's inconsistent curtailment settlement: rejected because it
  would weaken the common physical-delivery environment.

## Decision 8: Report directional FCR energy and library throughput

**Decision**: For requested and delivered FCR power `p` in charge-positive kW:

```text
upward_discharge_kwh = sum(max(-p, 0) * dt)
downward_charge_kwh = sum(max(p, 0) * dt)
signed_net_charge_positive_kwh = downward_charge - upward_discharge
```

Battery-terminal charge energy, discharge energy, and throughput are computed
from delivered combined battery power; throughput is charge plus discharge, not
the signed net.

**Rationale**: Directional totals remain non-negative and auditable. The
reference JSON supports parity for `y_in` and `y_out`, but not for directional
FCR energy or a standard throughput field. In particular,
`code/04_parse_results.jl` uses a study-specific efficiency-weighted throughput
label that is not adopted as the library definition.

**Alternatives considered**:

- Report only signed activation energy: rejected because opposite directions
  cancel and hide service volume.
- Claim parity for library throughput: rejected because the JSON does not expose
  that definition.

## Decision 9: Use a field-specific source-precision comparison

**Decision**: Preserve the library equation tolerance at `1e-6`. For the initial
reference artifact, treat every published `x0` and `xr` as an interval of
half a three-decimal unit (±0.0005 kW), propagate those intervals analytically
through each compared aggregate, and expand the published expected aggregate by
its own ±0.0005 output-rounding interval. Report:

- `exact` when the displayed rounded values are equal and no source uncertainty
  is needed;
- `source_precision_compatible` when the rigorous intervals overlap;
- `mismatch` when they do not overlap; or
- `unavailable` when the source artifact lacks the requested evidence.

For the 2023-06-18 fixture, conservative decision-only bounds are:

| Field family | Bound before expected-output ±0.0005 |
| --- | ---: |
| charge or discharge energy | 0.012970 kWh |
| stored-energy min/max/terminal | 0.014097 kWh |
| power extrema | 0.0007345 kW |
| day-ahead revenue | EUR 0.0010736 |
| FCR capacity revenue | EUR 0.0003798 |
| activation revenue | EUR 0.0000867 |
| combined FCR revenue | EUR 0.0004665 |
| total revenue | EUR 0.0015401 |

**Rationale**: `code/03_backtest_save.jl` rounds decisions and aggregates in the
same saved JSON. Midpoint replay of the published decisions yields terminal
55.483 versus 55.482 kWh, minimum 23.496 versus 23.495 kWh, maximum 58.580
versus 58.579 kWh, discharge 37.055 versus 37.056 kWh, and day-ahead 0.167
versus 0.168 EUR. Simple equality after rounding is therefore unsupported.

**Alternatives considered**:

- Use a blanket 0.01 or 0.001 tolerance: rejected because it is not derived per
  equation and can hide a real mismatch.
- Claim exact rounded equality from the current JSON: rejected by direct replay.
- Require Julia for every comparison: rejected because routine and ordinary
  evaluation must be fixture-backed. A future fixture refresh may export
  full-precision decisions and enable stricter comparison.

## Decision 10: Commit aggregate evidence, not the full activation dataset

**Decision**: Commit one small normalized Golden Reference Fixture containing
the reference commit, source paths, command, original JSON SHA-256, exact case
configuration, rounded `x0`/`xr`, prices, expected supported aggregates,
comparison bounds, mappings, source JSON pointers, dependency provenance, and an
external activation descriptor. Do not embed activation samples.

**Rationale**: This preserves routine provenance/schema/mapping checks without
redistributing the 529 MB source. The hand oracle validates all detailed replay
and settlement equations; the explicit external test supplies complete
reference-case evidence.

**Alternatives considered**:

- Commit the full CSV or the 2023-06-18 raw slice: rejected by the chosen
  redistribution boundary.
- Replace the missing activation with synthetic values in a reference-labelled
  fixture: rejected because it would create false parity evidence.
- Require an initialized submodule for routine tests: rejected because reference
  code is not a runtime dependency.

## Decision 11: Use the pinned README URL and fail closed on external data

**Decision**: Document this authoritative URL from the pinned README:

```text
https://github.com/lauinger/robust-storage-bidding/releases/download/v0.1/regulation_signal.csv
```

The OEL default local path is
`artifacts/reference/robust_storage_bidding/regulation_signal.csv`. The loader
requires an explicit path, exact size `528805941`, SHA-256
`0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13`,
header `DateTime,Frequency (Hz),xi,xi_EU`, exactly 8,640 selected rows, ten-second
cadence, unique timestamps, finite `xi_EU`, and the declared day. It never
downloads or falls back to `baselines/`.

**Rationale**: Pinned commit `7e44738` changed the README to the repository's
v0.1 release. `data/regulation_signal_info.txt` retains the superseded MV
location, so silently treating both as equivalent would obscure provenance.
Content identity, rather than URL availability, is the final acceptance gate.

**Alternatives considered**:

- Use the stale MV URL: rejected because it is superseded in the pinned README.
- Auto-download missing data: rejected because evaluation must be explicit and
  offline after user setup.
- Read the untracked file from the submodule by convention: rejected because the
  submodule may be absent and production code cannot depend on `baselines/`.

## Decision 12: Return a failed report before settlement

**Decision**: Evaluation performs deterministic preflight. Static
accepted-commitment eligibility covers schedule integrity, battery compatibility,
and bidirectional reserve power headroom without inspecting the realized
activation trajectory. A failure returns a `validation_failed` report with
ordered diagnostics, lineage, and a result fingerprint but no trace, settlement,
component profit, or total profit. A separately called diagnostic replay may
return physical samples and saturation evidence but is labelled invalid and is
never parity-comparable.

A plan that passes static eligibility may still reach a stored-energy bound under
the realized activation trace. That dynamic saturation remains settled, uses
delivered activation for revenue, applies only an explicit non-delivery penalty,
and remains outside the initial reference-parity domain.

**Rationale**: Existing Feature 010 diagnostic mode can replay failed commitments,
but its result still contains settlement. Reusing that object as normal bidder
performance would make invalid plans appear profitable. Separating the two
operations preserves diagnostic value and comparison integrity.

**Alternatives considered**:

- Raise for every invalid plan: rejected because the user requires a deterministic
  failed evaluation report.
- Set invalid profit to zero: rejected because zero is a valid economic value and
  would disguise unavailable settlement.

## Decision 13: Limit claims to real source evidence

**Decision**: Compare the rounded fixed decisions, total/DA/combined-FCR profit,
charge/discharge energy, stored-energy initial/min/max/terminal, and realized
power extrema under the source-precision policy. Objective value/bound remain
plan metadata. Solve time and `bilinear_violations` remain provenance only.
Detailed trace, tracking, non-delivery, saturation, directional FCR energy,
separate exact capacity/activation revenue, and library throughput are validated
by OEL invariants but marked unavailable for reference parity.

**Rationale**: The JSON does not contain the reference ten-second stored-energy
trace or those derived fields. For the restriction model,
`code/03_backtest_save.jl` records an empty bilinear-slack collection and reports
zero length; that zero is not an independent restriction-model calculation.
`results/result_overview.xlsx` is aggregate publication context, not per-day
execution evidence.

**Alternatives considered**:

- Infer detailed parity from aggregate agreement: rejected as unsupported.
- Treat objective EUR 11.028 as expected realized profit: rejected because the
  realized profit is EUR 10.749 and the concepts use different accounting.

## Decision 14: Preserve imports, markers, and Feature 010 fingerprints

**Decision**: Add public symbols through the existing lazy package-root export
pattern and extend its exact boundary tests. Register `external_reference_data`
and exclude it from routine CI selection. Run the full Feature 010 control,
simulator, manual, compatibility, real-replay, fixture-byte, import, lazy
dependency, and no-reference-import suites unchanged.

**Rationale**: Package-root export ordering and ownership are already asserted.
The broad simulator integration job currently collects all files, so an explicit
marker exclusion is needed in addition to an actionable skip in the optional
wrapper. Regression evidence must prove that refactoring the physical kernel does
not alter old output bytes or hashes.

**Alternatives considered**:

- Eagerly export the external adapter: rejected because a focused explicit import
  is sufficient and package roots must stay light.
- Let a missing CSV fail routine CI: rejected because the full source is
  intentionally not redistributed.
