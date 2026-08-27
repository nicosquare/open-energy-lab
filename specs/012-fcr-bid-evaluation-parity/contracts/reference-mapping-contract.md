# Robust-Storage-Bidding Reference Mapping Contract

## Reference Identity

“Reference implementation” means only the code/data at pinned commit
`7e44738bb30e5c8204efe40103b9be4c2203685c` under
`baselines/robust_storage_bidding/`.

Behavioral evidence is read from:

- `code/01_datastruct.jl`: sign, unit, battery, efficiency, and resolution
  declarations;
- `code/02_model.jl`: decision extension/indexing, price loading, SOC helpers,
  and objective meaning;
- `code/03_backtest_save.jl`, especially `bt_simulation`: realized combined
  power, stored energy, energy flow, settlement, and output rounding;
- `code/04_parse_results.jl`: downstream aggregate labels and their limitations;
- `results/02/2023-06-18.json`: generated fixed decisions, configuration, and
  aggregate expected evidence.

Production code never imports these paths. The committed Golden Reference
Fixture stores
them as provenance strings.

## Power And Activation Mapping

The reference is discharge-positive. For activation step `i` it uses:

```text
x_ref_requested[i] = x0_ref[h(i)] + xi_EU[i] * xr_ref[b(i)] + xa_ref[q(i)]
x_ref_delivered[i] = clip(x_ref_requested[i], -50, 50)
```

Experiment 2 has `xa_ref = 0`. Open Energy Lab is charge-positive and maps:

```text
baseline_oel[h] = -x0_ref[h]
capacity_oel[b] = xr_ref[b]
activation_oel[i] = xi_EU[i]
requested_fcr_oel[i] = -activation_oel[i] * capacity_oel[b(i)]
requested_combined_oel[i] = baseline_oel[h(i)] + requested_fcr_oel[i]
```

Therefore:

```text
requested_combined_oel[i] = -x_ref_requested[i]
```

`xr_ref` must be finite and non-negative. No sign is applied to it. Unknown
source signs or a caller-supplied alternative activation convention fail.

### Existing schedule reference fields

The reference mapper still calls the existing schedule builders. For FCR block
`b`, it assigns deterministic context references:

```text
volume_observation_ref = "reference_accepted_fcr_bid:b"
price_observation_ref = "reference_fcr_capacity_price:b"
```

The reference evaluation context resolves the first reference to the fixed
accepted `xr[b]` evidence in the generated result and the second to `pr[b]`.
This does not claim a system-wide contracted-market volume or an A81 observation.
Such a schedule is valid only with the matching reference-result adapter; passing
it to the Feature 010 `StackedServiceReplayRequest` fails its existing source-
specific reference validation as before.

## Battery Mapping

| Reference field | OEL value |
| --- | --- |
| `x̅ = 50 kW` | `max_discharge_kw = 50` |
| `x̲ = -50 kW` | `max_charge_kw = 50` |
| `y̅ = 90 kWh` | capacity `100 kWh`, `max_soc = 0.9` |
| `y̲ = 10 kWh` | capacity `100 kWh`, `min_soc = 0.1` |
| `y0 = 53.328 kWh` | `initial_soc = 0.53328` |
| `ηc = 0.92` | `charge_efficiency = 0.92` |
| `ηd = 0.92` | `discharge_efficiency = 0.92` |

Reference stored-energy update:

```text
y_next = y + dt * min(-eta_c * x_ref, -x_ref / eta_d)
```

After the power sign inversion this must equal the existing OEL battery
transition within `1e-6`. Stored energy in kWh is the parity value. SOC fraction
may be reported but is never substituted.

## Index And Coverage Mapping

The generated case declares:

| Grid | Count | Duration | Zero-based OEL mapping from activation index `i` |
| --- | ---: | --- | --- |
| activation | 8,640 | PT10S | `i` |
| checkpoint/planning | 96 | PT15M | `i // 90` |
| energy decision | 24 | PT1H | `i // 360` |
| FCR decision | 6 | PT4H | `i // 1440` |

This is equivalent to the reference's one-based ceiling indices. The final
sample belongs to energy interval 23, checkpoint 95, and FCR block 5. Counts,
boundaries, or order that do not agree fail before replay.

## Time Interpretation

The reference reads naive timestamps. Feature 012 declares them as the French
local delivery-day labels:

```text
local: 2023-06-18T00:00:00+02:00 / 2023-06-19T00:00:00+02:00
UTC:   2023-06-17T22:00:00Z / 2023-06-18T22:00:00Z
zone:  Europe/Paris
interval convention: start-inclusive/end-exclusive
```

The selected day is an ordinary 24-hour day. A 23-hour or 25-hour transition day
cannot use this profile and must fail with an unsupported-day diagnostic.

## Price And Revenue Units

| Reference value | Source basis | OEL conversion |
| --- | --- | --- |
| `p0[h]` | EUR/kWh, derived from EUR/MWh | `p0 * 1000` EUR/MWh |
| `pr[b]` | EUR/kW per four-hour block, derived from EUR/MW/4h | retain as EUR/kW/block, or `pr * 1000 / 4` EUR/MW/h |
| `x0`, `xr` | kW | sign rule above |
| `y`, `y_in`, `y_out` | kWh | identity |

For zero `xa` and no curtailment:

```text
reference_profit_da = sum(p0[h] * x0[h] * 1h)
reference_capacity = sum(pr[b] * xr[b])
reference_activation = sum(dt * p0[h(i)] * xi_EU[i] * xr[b(i)])
reference_profit_fcr = reference_capacity + reference_activation
reference_profit_total = reference_profit_da + reference_profit_fcr
```

OEL's charge-positive formulas yield the same signs. Unknown price bases, a
capacity price treated as hourly without dividing by four, or EUR/MWh used as
EUR/kWh fail.

## Aggregate Field Mapping

| Reference JSON field | OEL report field | Comparison rule |
| --- | --- | --- |
| `bt.curr.x0` | plan energy schedule powers after sign inversion | exact published decision mapping |
| `bt.curr.xr` | plan FCR capacities | exact published decision mapping |
| `bt.curr.profit_total` | settlement total profit | source precision |
| `bt.curr.profit_da` | day-ahead revenue | source precision |
| `bt.curr.profit_fcr` | capacity plus activation revenue | source precision |
| `bt.curr.profit_id` | reference configuration/provenance only | metadata; OEL intraday unavailable |
| `bt.curr.y_in` | delivered charge energy | source precision |
| `bt.curr.y_out` | delivered discharge energy | source precision |
| `bt.curr.soc_initial/min/max/terminal` | stored-energy fields in kWh | source precision |
| `bt.curr.xmin` | negative of OEL maximum delivered combined power | source precision |
| `bt.curr.xmax` | negative of OEL minimum delivered combined power | source precision |
| `objective value` / `objective bound` | plan optimization metadata | source metadata, not realized profit |
| `solve_time` | generation provenance | no parity assertion |
| `bilinear_violations` | generation provenance | no restriction-model parity assertion |

The initial artifact does not support reference comparison for a complete
ten-second state trajectory, tracking error, non-delivery, saturation causes,
directional FCR energy, separate exact capacity/activation revenue, or OEL
throughput.

## Shared Parity Domain

Reference-result parity requires all of the following:

- `energy_payment = true`, `intraday_trading = false`, `xi_signal = xi_EU`;
- `xa` and `xa_dec` are zero for the selected day;
- the declared battery, prices, schedule counts, activation, and period match;
- combined power does not require clipping and stored energy remains within
  10--90 kWh;
- only source-supported aggregate fields are requested; and
- the declared reference precision policy is applied.

Outside that domain, OEL behavior remains valid library behavior but not a
reference parity claim. In particular, OEL pays delivered activation energy,
whereas the reference `profit_fcr` uses requested `xi*xr`; they are equivalent
for this no-curtailment case only.
