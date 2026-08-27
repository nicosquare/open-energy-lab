# Data Model: FCR Bid-Evaluation Parity

**Feature**: `012-fcr-bid-evaluation-parity`
**Schema baseline**: v1
**Internal numeric tolerance**: absolute `1e-6`

## Conventions

- Library battery power is kW, positive for charge and negative for discharge.
- Stored energy is kWh and is the canonical battery-state parity unit.
- FCR activation is dimensionless; positive activation requests upward/discharge
  response through `requested_fcr_kw = -activation * capacity_kw`.
- Computation intervals are aware UTC half-open intervals. Reference delivery
  metadata uses `Europe/Paris` with explicit offsets.
- Currency is EUR. Day-ahead prices are canonical EUR/MWh. Reference FCR prices
  retain both their source EUR/MW/4h basis and converted EUR/kW/block value.
- Non-finite values are forbidden. Ordered tuples, not sets, carry diagnostics and
  comparison results.
- Existing Feature 010 schedules, activation traces, time contracts, battery
  components, replay samples, and fingerprints are reused rather than copied.

## Entity Relationships

```text
FixedFCRBidPlan
├── BidPlanProducer
├── EnergyBaselineSchedule ─┐
├── FCRCapacitySchedule ────┼── FCRBidEvaluationRequest
└── plan lineage/metrics    │   ├── evaluation market context
                            │   ├── RegulationActivationTrace
                            │   ├── BatteryComponent + MultiRateTimeContract
                            │   └── settlement/comparison selections
                            │
                            └── shared physical replay kernel
                                ├── ReferenceSettlementBreakdown
                                ├── DailyFCRBidEvaluationReport
                                └── ParityComparison (optional)

GoldenReferenceFixture
├── ReferenceDecisionMappingDeclaration
├── ExternalActivationDescriptor
├── ReferencePrecisionPolicy
└── ReferenceExpectedField[]
```

## Plan Entities

### BidPlanProducer

| Field | Type | Rules |
| --- | --- | --- |
| `producer_id` | string | non-empty stable identity |
| `producer_kind` | enum | `manual`, `heuristic`, `robust`, `tpm`, or `other` |
| `producer_version` | string | non-empty; code/config/artifact version |
| `configuration_fingerprint` | SHA-256 or unavailable | exact producer configuration, with reason if unavailable |

Producer kind is descriptive only. It cannot select different physical or
settlement behavior.

### OptimizationMetric

Discriminated value used independently for objective and bound.

| Field | Type | Rules |
| --- | --- | --- |
| `availability` | enum | `available` or `unavailable` |
| `value` | float/null | finite iff available |
| `unit` | string/null | required iff available; initial reference uses `EUR` |
| `unavailable_reason` | string/null | required iff unavailable |
| `meaning` | string | `optimization_objective` or `optimization_bound` |

An unavailable metric is valid for manual and heuristic plans. Neither metric is
realized profit.

### PlanDiagnostic

| Field | Type | Rules |
| --- | --- | --- |
| `code` | string | stable machine-readable code |
| `severity` | enum | `info`, `warning`, or `error` |
| `field_path` | string/null | canonical path when field-specific |
| `message` | string | deterministic, credential-free text |
| `evidence_refs` | tuple[string] | deterministic order |

Diagnostics are ordered by validation phase, then field path, code, and evidence
reference. Human text is included in fingerprints only through the declared plan
semantics version.

### FixedFCRBidPlan

| Field | Type | Rules |
| --- | --- | --- |
| `plan_id` | string | non-empty |
| `semantics_version` | string | initial `oel.fixed-fcr-bid-plan.v1` |
| `producer` | `BidPlanProducer` | exactly one |
| `information_cutoff_utc` | aware UTC timestamp | cannot be after any producer-visible input |
| `energy_schedule` | existing `EnergyBaselineSchedule` | exact object reference; complete hourly coverage |
| `fcr_schedule` | existing `FCRCapacitySchedule` | exact object reference; complete PT4H coverage |
| `producer_input_fingerprints` | ordered mapping | only inputs available by cutoff; no realized activation |
| `solve_status` | enum | `not_applicable`, `optimal`, `feasible`, `infeasible`, `failed`, `unknown` |
| `objective` | `OptimizationMetric` | exact availability semantics |
| `objective_bound` | `OptimizationMetric` | exact availability semantics |
| `diagnostics` | tuple[`PlanDiagnostic`] | deterministic order |
| `plan_fingerprint` | SHA-256 | all preceding semantic values plus schedule fingerprints |

The in-memory entity retains the two exact schedule objects. Its serialized plan
view contains `schedule_id`, `semantics_version`, and `schedule_fingerprint`
references only; it never repeats interval values. A caller resolving a serialized
plan supplies the schedules separately and both references must match.

The plan deliberately contains no evaluation activation fingerprint. Complete
lineage is added by `FCRBidEvaluationRequest` after the information cutoff.

## Evaluation Input Entities

### ReferencePriceObservation

| Field | Type | Rules |
| --- | --- | --- |
| `interval` | `CanonicalInterval` | exact PT1H or PT4H interval |
| `price_kind` | enum | `day_ahead_energy` or `fcr_capacity` |
| `source_value` | finite float | retained exactly from reference fixture |
| `source_unit` | string | `EUR/kWh` or `EUR/kW/4h` |
| `canonical_value` | finite float | converted EUR/MWh or EUR/kW/block |
| `conversion_id` | string | declared formula version |
| `source_ref` | string | Golden Reference Fixture JSON pointer/provenance reference |

### EvaluationMarketContext

Discriminated market/accounting context; it is not part of the plan.

| Field | Type | Rules |
| --- | --- | --- |
| `context_kind` | enum | `feature_010_market_artifact` or `reference_result` |
| `semantics_version` | string | explicit and fingerprinted |
| `period` | `CanonicalInterval` | exact replay horizon |
| `day_ahead_prices` | tuple | complete PT1H coverage |
| `fcr_capacity_prices` | tuple | complete PT4H coverage |
| `accepted_bid_evidence` | ordered mapping | observed Feature 010 market-volume refs or fixed reference-result acceptance evidence |
| `source_fingerprints` | ordered mapping | complete input lineage |
| `context_fingerprint` | SHA-256 | semantic content |

The Feature 010 variant references one existing `MarketDataArtifact`. The
reference-result variant cites the accepted fixed `xr` decisions and source JSON;
it does not claim an observed A81 contracted volume.

### FCRBidEvaluationRequest

| Field | Type | Rules |
| --- | --- | --- |
| `evaluation_id` | string | non-empty |
| `semantics_version` | string | initial `oel.fcr-bid-evaluation.v1` |
| `plan` | `FixedFCRBidPlan` | exactly one |
| `market_context` | `EvaluationMarketContext` | exact horizon and schedule refs |
| `activation_trace` | existing `RegulationActivationTrace` | exact horizon/resolution |
| `battery` | existing `BatteryComponent` | one battery; fingerprinted at request construction and rechecked before replay |
| `time_contract` | existing `MultiRateTimeContract` | PT10S/PT15M/PT1H/PT4H for reference case |
| `settlement_profile` | enum/version | Feature 010 default or explicit reference-result v1 |
| `penalty_rule` | existing rule/null | exact configured meaning |
| `terminal_soc_target` | existing target/null | report-only |
| `comparison_fixture` | `GoldenReferenceFixture`/null | optional and explicit |
| `numeric_tolerance` | float | finite, positive; initial `1e-6` |
| `evaluation_input_fingerprint` | SHA-256 | plan plus every evaluation-only semantic input |

Construction validates that the request contains the same schedule objects and
fingerprints as the plan. The activation fingerprint is evaluation-only and must
not appear in `producer_input_fingerprints`.

## Reference Mapping And Fixture Entities

### ReferenceDecisionMappingDeclaration

| Field | Type | Rules |
| --- | --- | --- |
| `mapping_id` | string | initial `robust-storage-bidding-to-oel-v1` |
| `reference_commit` | SHA-1 | exact pinned commit |
| `source_fields` | ordered mapping | JSON pointers for `x0`, `xr`, prices, battery, outputs |
| `source_sign_convention` | string | discharge-positive |
| `target_sign_convention` | string | charge-positive |
| `x0_formula` | string | exact sign inversion |
| `xr_formula` | string | exact non-negative identity mapping |
| `activation_formula` | string | exact combined-power equivalence |
| `unit_conversions` | tuple | complete price/power/energy rules |
| `index_conversions` | tuple | 24/6/96/8,640 and one-based/zero-based declarations |
| `source_timezone_interpretation` | string | naive Europe/Paris ordinary delivery day |
| `target_period` | `CanonicalInterval` | explicit UTC/local period |
| `mapping_fingerprint` | SHA-256 | all semantic content |

Unknown sign, unit, timezone, price basis, or indexing fails mapping.

### ExternalActivationDescriptor

| Field | Type | Rules |
| --- | --- | --- |
| `input_id` | string | stable |
| `download_url` | HTTPS URL | pinned README v0.1 URL |
| `local_relative_path` | POSIX path | `artifacts/reference/robust_storage_bidding/regulation_signal.csv` |
| `byte_count` | integer | exactly `528805941` |
| `sha256` | SHA-256 | exactly `0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13` |
| `header` | tuple[string] | exact four columns |
| `selected_date` | date | `2023-06-18` |
| `selected_column` | string | `xi_EU` |
| `selected_resolution` | duration | `PT10S` |
| `selected_row_count` | integer | `8640` |
| `retention_status` | enum | `external_only` |
| `redistribution_policy` | mapping | no repository/package/release/mirror/CI artifact |

The descriptor is committed; the CSV is not. The loader accepts an explicit path,
performs no network request, and returns a domain error for every mismatch.

### ReferencePrecisionPolicy

| Field | Type | Rules |
| --- | --- | --- |
| `policy_id` | string | initial `rounded-decisions-interval-v1` |
| `decision_decimal_places` | integer | `3` |
| `aggregate_decimal_places` | integer | `3` |
| `decision_half_unit_kw` | float | `0.0005` |
| `aggregate_half_unit` | float | `0.0005` in each field's unit |
| `propagation_method` | string | analytic field-specific interval bound |
| `field_bounds` | ordered mapping | formula, evaluated bound, unit, dependencies |
| `exact_rounding_mode` | enum | `record_only`, until unrounded decisions exist |
| `policy_fingerprint` | SHA-256 | all semantic content |

### ReferenceExpectedField

| Field | Type | Rules |
| --- | --- | --- |
| `field_id` | string | canonical OEL report path or provenance path |
| `reference_field_path` | string | exact source JSON pointer |
| `expected_value` | scalar | finite numeric or exact nonnumeric value |
| `unit` | string/null | required for numeric physical/economic fields |
| `evidence_kind` | enum | `parity`, `metadata`, or `unavailable` |
| `comparison_rule` | enum | exact, source-precision, metadata-only, unavailable |

### GoldenReferenceFixture

| Field | Type | Rules |
| --- | --- | --- |
| `schema_version` | string | `oel.fcr-reference-aggregate.v1` |
| `fixture_id` | string | stable 2023-06-18 identity |
| `reference_commit` | SHA-1 | pinned value |
| `generation_command` | string | exact command and working-directory declaration |
| `original_result_path` | string | reference-relative path |
| `original_result_sha256` | SHA-256 | `8c13f831...ddc1e6` |
| `reference_source_paths` | tuple[string] | exact behavioral evidence paths |
| `reference_configuration` | ordered mapping | model, flags, battery, grids, prices |
| `rounded_x0_kw` | 24 finite floats | source order |
| `rounded_xr_kw` | 6 non-negative floats | source order |
| `mapping` | `ReferenceDecisionMappingDeclaration` | exact version |
| `external_activation` | `ExternalActivationDescriptor` | no embedded samples |
| `precision_policy` | `ReferencePrecisionPolicy` | explicit |
| `expected_fields` | tuple[`ReferenceExpectedField`] | deterministic field order |
| `runtime_provenance` | ordered mapping | documented and locked versions distinguished |
| `redistribution_status` | ordered mapping | per input/derived field |
| `fixture_fingerprint` | SHA-256 | all semantic content except self |

The routine fixture loader never resolves `original_result_path`, any baseline
path, or the external CSV. Those strings are provenance only.

## Settlement And Report Entities

### DirectionalFCREnergy

| Field | Type | Rules |
| --- | --- | --- |
| `upward_discharge_kwh` | float | finite, non-negative |
| `downward_charge_kwh` | float | finite, non-negative |
| `signed_net_charge_positive_kwh` | float | downward minus upward within `1e-6` |

One value exists for requested FCR and one for delivered FCR.

### ComponentAvailability

| Field | Type | Rules |
| --- | --- | --- |
| `status` | enum | `available` or `unavailable` |
| `value_eur` | float/null | finite iff available |
| `reason` | string/null | required iff unavailable |

Intraday, imbalance, degradation, and terminal-value components are unavailable
in reference profile v1. Configured absence of a penalty rule is an available
zero penalty with an explicit `no_penalty_rule` identity, not a silent default.

### ReferenceSettlementBreakdown

| Field | Type | Rules |
| --- | --- | --- |
| `profile_id` | string | `robust-storage-bidding-reference-settlement-v1` |
| `day_ahead_revenue` | `ComponentAvailability` | available |
| `fcr_capacity_revenue` | `ComponentAvailability` | available |
| `activation_energy_revenue` | `ComponentAvailability` | available iff energy payment enabled |
| `penalty` | `ComponentAvailability` | available for configured rule/absence |
| `intraday`, `imbalance`, `degradation`, `terminal_value` | `ComponentAvailability` | unavailable in v1 |
| `charge_energy_kwh` | float | delivered combined charge |
| `discharge_energy_kwh` | float | delivered combined discharge |
| `throughput_kwh` | float | charge plus discharge |
| `total_profit_eur` | float | available component reconciliation |
| `reconciliation_error_eur` | float | absolute value <= request tolerance |
| `settlement_fingerprint` | SHA-256 | full profile and values |

### DailyPhysicalMetrics

Contains:

- initial, minimum, maximum, and terminal stored energy in kWh;
- optional normalized initial/min/max/terminal SOC;
- minimum/maximum requested and delivered combined power;
- requested and delivered `DirectionalFCREnergy`;
- signed and absolute tracking summaries and non-delivery energy;
- charge energy, discharge energy, and throughput;
- saturation counts, durations, event references, and physical-limit diagnostics;
- 24/6/96/8,640 counts.

Every metric is derived from the existing replay samples/checkpoints, never from
the reference expected result.

### DailyFCRBidEvaluationReport

Discriminated immutable result.

| Field | Successful | Validation failed |
| --- | --- | --- |
| `status` | `settled` | `validation_failed` |
| plan/producer/cutoff | required | required |
| ordered diagnostics | required | required |
| physical trace/ref | required | absent |
| `DailyPhysicalMetrics` | required | absent |
| settlement | required | absent |
| total/component profit | required | absent |
| parity comparison | optional | unavailable/not-run only |
| plan/input/trace/settlement/result fingerprints | required | plan/input/result required; trace/settlement absent |

No numeric zero substitutes for an absent failed-evaluation field.

Static accepted-commitment validation covers schedule integrity, battery
compatibility, and bidirectional reserve power headroom without inspecting the
realized activation trajectory. Dynamic stored-energy saturation after this
gate remains `settled`, reports delivered/non-delivered quantities, and is
outside the initial reference-parity domain. Static gate failures alone use
`validation_failed` and may be investigated through the separate diagnostic
replay.

### ParityFieldResult

| Field | Type | Rules |
| --- | --- | --- |
| `field_id` | string | canonical report path |
| `reference_field_path` | string/null | source evidence path |
| `expected_value` / `actual_value` | scalar/null | preserved at full available precision |
| `unit` | string/null | exact |
| `comparison_status` | enum | `exact`, `source_precision_compatible`, `mismatch`, `unavailable` |
| `actual_interval` / `expected_interval` | pair/null | required for source-precision comparison |
| `exact_rounded_match` | bool/null | separately recorded |
| `applied_rule` | string | mapping and precision policy IDs |
| `diagnostics` | tuple | ordered |

### ParityComparison

| Field | Type | Rules |
| --- | --- | --- |
| `comparison_id` | string | stable |
| `mapping_fingerprint` | SHA-256 | exact mapping |
| `precision_policy_fingerprint` | SHA-256 | exact policy |
| `fixture_fingerprint` | SHA-256 | exact expected evidence |
| `field_results` | tuple[`ParityFieldResult`] | canonical declared field order |
| `overall_status` | enum | `compatible`, `mismatch`, or `insufficient_evidence` |
| `comparison_fingerprint` | SHA-256 | all preceding semantic values |

`compatible` permits `exact` and `source_precision_compatible` fields only.
Any `mismatch` makes the overall result `mismatch`. Requested unavailable fields
produce `insufficient_evidence` unless they were explicitly declared outside the
requested parity domain.

## State Transitions

```text
plan constructed
  ├── plan validation error -> no plan
  └── valid frozen plan
        └── evaluation request bound after cutoff
              ├── preflight fails -> validation_failed report (no profit)
              │     └── optional separate diagnostic replay (invalid label)
              └── preflight passes -> physical replay
                    └── selected settlement reconciles
                          ├── no expected fixture -> settled report
                          └── expected fixture -> parity comparison -> settled report
```

An immutable report never transitions in place. A repeated operation constructs
an equal report with the same ordered bytes and fingerprints.

## Fingerprint Boundaries

- `plan_fingerprint`: producer-known plan semantics and schedule references.
- `evaluation_input_fingerprint`: plan plus market, activation, battery, time,
  settlement, penalty, target, tolerance, and optional fixture identities.
- Existing Feature 010 `trace_fingerprint`: unchanged for its existing wrapper.
- New evaluation `trace_fingerprint`: exact shared-kernel detailed trace under the
  evaluation semantics version.
- `settlement_fingerprint`: selected profile and reconciled components.
- `comparison_fingerprint`: expected evidence, mapping, precision, and field
  outcomes.
- `result_fingerprint`: report discriminant, diagnostics, metrics/availability,
  lineage, and preceding component fingerprints.
