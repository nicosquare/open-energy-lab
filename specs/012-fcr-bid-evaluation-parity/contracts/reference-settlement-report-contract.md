# Reference Settlement And Daily Report Contract

## Profile Selection

Reference accounting is selected explicitly by profile ID:

```text
robust-storage-bidding-reference-settlement-v1
```

Absence of that selection preserves Feature 010's existing default settlement,
including `activation_energy_settlement_status = not_modeled`, its public result
shape, and all existing fingerprints.

The profile ID, energy-payment flag, price basis, penalty rule, and all component
availability states are fingerprint inputs.

## Component Formulas

For charge-positive library power:

```text
day_ahead_revenue_eur =
    -sum(baseline_kw[h] * duration_h[h] * price_eur_per_mwh[h] / 1000)

fcr_capacity_revenue_eur =
    sum(capacity_kw[b] * price_eur_per_kw_per_block[b])

activation_energy_revenue_eur =
    -sum(delivered_fcr_kw[i] * duration_h[i] * price_eur_per_kwh[h(i)])

penalty_eur = configured_rule(non_delivery and rule inputs)

total_profit_eur =
    day_ahead_revenue_eur
    + fcr_capacity_revenue_eur
    + activation_energy_revenue_eur
    - penalty_eur
```

Requested but undelivered FCR energy earns no activation payment. A configured
penalty operates separately and cannot modify delivered power.

Every available component is computed at full library precision. The absolute
component-to-total reconciliation error must be at most the request tolerance,
initially `1e-6`; otherwise evaluation fails rather than publishing a settled
report.

## Component Availability

| Component | Reference profile v1 |
| --- | --- |
| day-ahead energy | available |
| FCR capacity | available |
| delivered activation energy | available when `energy_payment=true` |
| configured non-delivery penalty | available, including explicit no-rule zero |
| intraday settlement | unavailable |
| imbalance settlement | unavailable |
| degradation cost | unavailable |
| terminal value | unavailable |

Unavailable components contain no numeric zero. Each carries a stable reason.
The pinned reference's `profit_id = 0.000` proves its configuration, not the
availability of a general OEL intraday settlement model.

## Energy And Power Metrics

Battery-terminal energy is derived from delivered combined power:

```text
charge_energy_kwh = sum(max(delivered_combined_kw, 0) * dt)
discharge_energy_kwh = sum(max(-delivered_combined_kw, 0) * dt)
throughput_kwh = charge_energy_kwh + discharge_energy_kwh
```

For requested or delivered FCR power `p_fcr`:

```text
upward_discharge_kwh = sum(max(-p_fcr, 0) * dt)
downward_charge_kwh = sum(max(p_fcr, 0) * dt)
signed_net_charge_positive_kwh = downward_charge_kwh - upward_discharge_kwh
```

Directional values are non-negative. Signed net must reconcile with them within
`1e-6`. Throughput is never inferred from signed net.

Report power extrema separately for requested and delivered combined power.
Reference power parity applies the sign/bound reversal in the mapping contract.

## Successful Daily Report

A settled report contains, in deterministic field order:

1. schema/evaluation/profile versions and status;
2. plan, schedule, producer, solve-status, objective/bound, and cutoff identity;
3. market, activation, battery, time, penalty, and expected-fixture lineage;
4. 24/6/96/8,640 interval counts;
5. initial/min/max/terminal stored energy in kWh and optional SOC fractions;
6. requested and delivered combined-power extrema;
7. requested and delivered upward/downward/net FCR energy;
8. charge energy, discharge energy, and throughput;
9. signed/absolute tracking and non-delivery totals;
10. saturation samples/events/durations and ordered physical-limit diagnostics;
11. settlement component availability and values;
12. optional field-level parity comparison;
13. plan, input, trace, settlement, comparison, and result fingerprints.

The detailed trace remains the existing chronological replay evidence. Daily
metrics are computed from it and checked against checkpoint, hourly, and FCR
aggregations. Expected reference values never feed actual metrics.

## Failed Daily Report

If accepted-commitment or input validation fails, report:

- `status = validation_failed`;
- plan/producer/cutoff/schedule identity;
- evaluation input fingerprint where constructible;
- deterministic ordered validation diagnostics;
- unavailable comparison status; and
- deterministic result fingerprint.

The report must omit trace, physical metrics, settlement, and profit. It may not
contain `0.0` placeholders. A diagnostic replay is a separate invalid object and
cannot be passed to settlement or comparison.

## Reference FCR Reconciliation

When the pinned fixture supplies `profit_fcr`, compare:

```text
oel_fcr_combined = fcr_capacity_revenue + activation_energy_revenue
```

to the reference combined field under the reference precision policy. The OEL
components remain individually inspectable, but the source artifact supports
only their combined realized parity. Separate capacity and activation values are
library calculations, not independently observed reference outputs.

## Reference Comparison Outcomes

Each requested field records expected/actual values, units, mapping, precision
rule, exact rounded-match flag, intervals when applicable, diagnostics, and one
status:

- `exact`;
- `source_precision_compatible`;
- `mismatch`; or
- `unavailable`.

The initial source-precision rule treats each rounded decision as ±0.0005 kW,
uses an analytic field-specific propagated bound, and treats each published
aggregate as its displayed value ±0.0005 in that field's unit. Interval overlap
is compatible. A single blanket tolerance is forbidden.

Comparison cannot be requested for a failed evaluation. Unsupported trace or
derived fields return `unavailable`; they are never inferred from aggregate
agreement.

## Hand-Calculable Oracle

The routine oracle independently asserts every intermediate and aggregate for:

- reference `x0` sign inversion and unchanged non-negative `xr`;
- positive and negative activation direction;
- efficiency-aware stored-energy transitions;
- delivered activation-energy settlement;
- day-ahead and FCR capacity revenue;
- charge/discharge/throughput and directional FCR energy;
- requested/delivered tracking and non-delivery;
- valid settled dynamic SOC saturation, non-delivery, and diagnostics;
- statically failed accepted-commitment reporting and separate diagnostic
  replay; and
- component-to-total reconciliation.

Expected values are authored arithmetic, not generated by the evaluator under
test, and use absolute `1e-6` assertions.

## Determinism And Fingerprints

Repeated evaluation with identical semantic inputs must reproduce identical
ordered trace values, metrics, diagnostics, availability states, comparison
fields, canonical bytes, and fingerprints. No output contains wall-clock
generation time unless it is explicit input provenance and therefore part of the
input identity.
