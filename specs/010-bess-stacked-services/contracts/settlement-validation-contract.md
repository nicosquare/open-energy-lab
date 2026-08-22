# Settlement And Validation Contract

## Settlement Ownership

`open_energy_lab.simulator.fcr_settlement` owns realized first-release
settlement after replay alignment. It consumes fixed schedules, aligned market
observations, and canonical non-delivery. It does not alter physical dispatch.

## Day-Ahead Energy Revenue

For each accepted energy interval:

```text
energy_mwh = baseline_power_kw * duration_h / 1000
energy_revenue_eur = -energy_mwh * day_ahead_price_eur_per_mwh
```

Positive charge is a cost; negative discharge is revenue. Settlement uses the
accepted schedule, not delivered combined power or activation energy.

## FCR Capacity Revenue

For each eligible commitment interval:

```text
capacity_mw = committed_capacity_kw / 1000
fcr_revenue_eur = capacity_mw * duration_h * price_eur_per_mw_h
```

The commitment must already have passed market-volume, price, block, and power
headroom validation. Physical non-delivery does not silently reduce capacity
revenue.

## Penalty

No configured rule means `penalty_eur == 0`.

The v1 nonzero research rule is:

```text
penalty_eur = sum(absolute_fcr_non_delivery_energy_kwh)
              * rate_eur_per_kwh
```

Rule ID, measure, rate, unit, and per-substep summation basis are persisted.
The measure is canonical non-delivery relative to the accepted baseline.

## Throughput And Profit

```text
throughput_kwh = sum(abs(delivered_combined_power_kw) * duration_h)
total_profit_eur = day_ahead_energy_revenue_eur
                   + fcr_capacity_revenue_eur
                   - penalty_eur
```

Throughput is battery-terminal charge plus discharge energy. It is not a cost
in v1. Activation-energy payment, imbalance settlement, degradation cost, and
terminal SOC value are explicitly `not_modeled`.

## Manual Oracle

The required four-hour fixture is:

```text
battery: 4 kWh, [0, 4] kWh, initial 2 kWh, +/-2 kW, eta_c=eta_d=1
energy baseline kW: [+1, 0, 0, -1] over four one-hour intervals
FCR: 1 kW for one four-hour block
activation: [+1, -1, 0, 0, 0, 0, +1, -1] over eight half-hours
day-ahead price EUR/MWh: [50, 60, 70, 100]
FCR price: 20 EUR/MW/h
penalty: none
```

Expected within `1e-6`:

```text
requested/delivered combined kW: [0, +2, 0, 0, 0, 0, -2, 0]
stored energy kWh incl. initial: [2, 2, 3, 3, 3, 3, 3, 2, 2]
throughput: 2 kWh
energy revenue: EUR 0.05
FCR capacity revenue: EUR 0.08
tracking error and penalty: 0
total profit: EUR 0.13
```

Every expected value is asserted independently; total-profit agreement alone
is insufficient.

## Recorded Real Demonstration

Selected period:

```text
Europe/Paris [2022-08-19 00:00:00+02:00, 2022-08-20 00:00:00+02:00)
UTC          [2022-08-18 22:00:00Z,      2022-08-19 22:00:00Z)
```

Acceptance requires:

- ENTSO-E-produced, complete, compatible A44/combined-A81 normalized artifact
- separately provenanced RTE-derived PT10S activation artifact
- 24 energy intervals, 96 checkpoint intervals, 6 FCR blocks, 8,640 samples
- fixed demonstration battery, schedules/heuristic config, zero penalty, and
  optional report-only terminal target as specified in `research.md`
- recorded input, trace, and result fingerprints plus component totals
- documented attribution and restricted private-repository storage policy for
  every committed real-data artifact

Two offline runs must have zero transport calls and identical traces, event
ordering, settlement components, throughput, terminal report, and fingerprints.

If A44/combined-A81 completeness or the restricted-storage policy fails for
this period, the real fixture is blocked. Public/package distribution,
synthetic completion, and silent alternative sources are forbidden.

## Required Offline Validation Matrix

### Source and artifact

- invalid/missing authentication; permanent one attempt
- timeout/connection/408/429/5xx; no more than three attempts
- valid and invalid retry delays
- acknowledgement, empty response, missing required series
- gap, overlap, exact duplicate, conflicting duplicate
- wrong area/process/business/direction/product
- unknown curve, unexpected resolution, incompatible unit/currency
- 23-hour and 25-hour local delivery days with explicit fold/gap handling
- revision regression and non-comparable revisions
- token sentinel scan
- digest-only and permitted-sidecar paths
- unknown schema and integrity/sidecar failure
- atomic failure with no partial manifest

### Activation and alignment

- interval-average and explicit left-hold conversions
- gap, duplicate, ambiguous timezone, out-of-range/non-finite value
- incompatible meaning or resolution
- partial horizon and non-integer multi-rate mapping
- A83/A84 rejection without semantic proof

### Replay and settlement

- exact manual oracle
- power and SOC saturation with causes
- requested/delivered FCR attribution reconciliation
- direct versus aggregated energy conservation
- zero-FCR arbitrage compatibility
- zero-energy regulation-only behavior and centered initial SOC
- stacked headroom clipping and activation-lookahead independence
- explicit nonzero penalty and absent-rule zero penalty
- report-only terminal target
- recorded one-day replay for all five measured runs under the Reference
  Benchmark Protocol in `plan.md`, with every run under 10 seconds

## Routine Commands

Routine checks are offline:

```bash
uv run pytest tests/unit/market tests/integration/market -m "not live_entsoe"
uv run pytest tests/unit/control tests/unit/simulator
uv run pytest tests/integration/control tests/integration/simulator -m "not reference_benchmark"
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
```

The credentialed live ENTSO-E check and hardware-specific reference benchmark
are separately selected and are never part of the routine command group.
