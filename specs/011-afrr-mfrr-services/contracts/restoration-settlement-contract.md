# Restoration Settlement and Validation Contract

## Settlement Ownership

Settlement consumes a completed physical aFRR or mFRR replay plus explicit
prices/rules. It does not alter schedules, battery requests, delivery, or
non-performance. Feature 010 FCR settlement remains unchanged.

## Availability Gate

Before calculating money, validate every price and rule declared required by
the study for product, direction, unit, currency, interval coverage, and
eligibility. Then choose one atomic state:

- `AVAILABLE`: every required input is present and compatible; all components,
  gross revenue, and total net result are returned
- `UNAVAILABLE`: physical replay remains valid, but no monetary component set,
  gross revenue, partial total, or net result is presented as complete

Unavailable diagnostics name the source/field/rule, product/direction, requested
period, observed condition, and expected contract. Missing is never zero.

## Day-ahead Energy Revenue

Use accepted energy-baseline power/energy and explicit covered day-ahead price,
not realized combined battery power. Apply the project's charge-positive sign
and import/export settlement convention explicitly. A zero baseline produces
zero day-ahead energy revenue under a valid declared rule.

## Capacity Revenue

Calculate separately by direction:

```text
capacity_revenue = eligible_committed_capacity * covered_duration * compatible_capacity_price
```

The concrete equation accounts for the price's declared denominator (for
example EUR/MW/h versus EUR/MW/15min) and converts kW/MW exactly once. Ineligible
capacity contributes zero with explicit ineligibility status. No unconfigured
price or area aggregate is inferred.

## Activated-energy Revenue

Use delivered eligible balancing energy, not requested area quantity:

```text
directional_revenue = delivered_activation_mwh * compatible_eur_per_mwh
```

Upward and downward energy/revenue remain separate. mFRR SA and DA may have
different compatible price series and retain type identity in the audit.

## Area Price Proxy

A compatible RTE weighted-average, clearing, or settlement price may settle a
derived simulation only through an explicit `AreaPriceProxyMapping` that pins:

- source artifact and series fingerprint
- RTE field and semantic definition
- product, direction, and covered interval
- unit/currency transformation
- derived activation mapping fingerprint
- label `scenario_proxy`

Every table, plot, repr, and result states that it is a simulated area-price
proxy, not an observed BESS invoice. Price presence never authorizes deriving an
activation request.

For the real aFRR demonstration, the matching upward weighted-average price may
be used per PT15M interval. For the selected real mFRR SA demonstration, the
downward `clearing_price=64.83 EUR/MWh` may be used as the labelled proxy. Null
DA settlement fields remain unavailable and are not substituted.

## Non-performance Penalty

An optional rule declares product, direction applicability, event/period basis,
shortfall measure, rate/price, unit, and covered period. Apply it only to the
declared delivered-versus-requested shortfall. With no rule, penalty equals zero
and status is `UNCONFIGURED`; this is not a claim about real French market
penalties.

## Throughput and Degradation

```text
throughput_kwh = absolute_delivered_charge_kwh + absolute_delivered_discharge_kwh
degradation_cost = throughput_kwh * configured_cost_per_kwh
```

The cost must be finite and non-negative. With no rule, cost is zero and status
is `UNCONFIGURED`. Documentation and results call it a first-order comparison
proxy, not electrochemical aging or lifetime prediction.

## Reconciliation

When available:

```text
gross_revenue =
    day_ahead_energy_revenue
  + upward_capacity_revenue
  + downward_capacity_revenue
  + upward_activation_revenue
  + downward_activation_revenue

net_result = gross_revenue - non_performance_penalty - degradation_cost
```

The selected product is explicit. Components for the unselected restoration
product are absent, not zero-valued entries. Reconciliation must hold within
absolute tolerance `1e-6` and be part of result validation.

## Zero Activation

Under a valid declared settlement:

- upward/downward activated energy is zero
- upward/downward activated-energy revenue is zero
- activation non-performance is zero
- eligible capacity revenue may remain nonzero
- baseline day-ahead revenue remains independently determined
- degradation may reflect baseline throughput but not balancing throughput

## Fingerprint

The settlement fingerprint includes replay-result fingerprint, product,
availability and reasons, every price/rule/proxy fingerprint, units, coverage,
component values/statuses, tolerance, and reconciliation version. It excludes
credentials, output paths, current source state, and runtime objects.

## Required Validation Matrix

Tests independently prove:

- aFRR upward/downward capacity and activation revenue
- mFRR upward/downward and SA/DA compatible settlement
- zero activation behavior
- missing, null, wrong-direction, wrong-product, wrong-unit, ambiguous, and
  incomplete price make the whole settlement unavailable
- no partial total appears when unavailable
- explicit no-penalty and no-degradation status
- penalty and degradation equations
- area-price proxy labelling and fingerprint lineage
- exact gross/net reconciliation
- FCR settlement types and reference outputs remain unchanged
