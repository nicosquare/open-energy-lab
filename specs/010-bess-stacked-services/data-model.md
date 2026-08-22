# Data Model: French BESS Stacked Services

**Feature**: `010-bess-stacked-services`  
**Schema baseline**: v1  
**Default numeric tolerance**: `1e-6`

## Conventions

- All computation intervals are aware UTC half-open intervals
  `[start_utc, end_utc)`.
- France delivery metadata uses IANA timezone `Europe/Paris` and preserves the
  local label, UTC offset, and fold value for each boundary.
- Battery power and reserve schedules use kW. Positive battery power means
  charging; negative means discharging.
- Stored energy and throughput use kWh.
- Market volume uses MW, energy price uses EUR/MWh, and canonical FCR capacity
  price uses EUR/MW/h.
- Activation is dimensionless in `[-1, 1]`; positive means upward/discharge.
- JSON timestamps use ISO 8601 with `Z` for UTC and an explicit numeric offset
  for local delivery labels.
- Non-finite JSON numbers are forbidden.

## Market-Data Production Entities

### EntsoeMarketDataRequest

Token-free description of one explicit source operation.

| Field | Type | Rules |
| --- | --- | --- |
| `profile_id` | string | Exactly `fr-day-ahead-symmetric-fcr-v1` |
| `area_eic` | string | Exactly `10YFR-RTE------C` |
| `market_timezone` | string | Exactly `Europe/Paris` |
| `requested_start_utc` | aware instant | Inclusive |
| `requested_end_utc` | aware instant | Exclusive and greater than start |
| `source_endpoint` | string | HTTPS origin and path only; no query or credential |
| `window_policy` | object | Enclosing local delivery days, deterministic order |
| `raw_retention_policy` | enum | `digest_only` or `permitted_sidecar` |
| `normalization_version` | string | Non-empty and persisted |

The API token is a separate call argument and is never a field, property,
representation, equality component, or fingerprint input.

### SourceQueryWindow

One source and series request attempted by the transport.

| Field | Type | Rules |
| --- | --- | --- |
| `window_id` | string | Token-free deterministic ID |
| `document_type` | enum | `A44`, `A81`, or `A89` |
| `process_type` | string/null | Profile-required value when supported |
| `business_type` | string/null | `A95` for FCR documents |
| `market_agreement_type` | string/null | `A01` daily agreement for A81/A89 |
| `area_parameter` | string | Bidding-zone pair or control area, as appropriate |
| `start_utc` / `end_utc` | aware instant | Enclosing local-day source window |
| `attempt_count` | integer | Result metadata; 1 through 3 |

The persisted request identity contains these semantic fields, never the final
wire URL or headers.

### RawResponseEvidence

Evidence for one returned byte response.

| Field | Type | Rules |
| --- | --- | --- |
| `response_id` | string | Unique within artifact |
| `window_id` | string | References `SourceQueryWindow` identity |
| `retrieved_at_utc` | aware instant | Retrieval provenance |
| `media_type` | string | Expected XML-compatible media type |
| `byte_count` | integer | Positive and within configured bound |
| `sha256` | string | 64 lowercase hexadecimal characters |
| `retention_status` | enum | `digest_only` or `sidecar_retained` |
| `redistribution_basis` | object | Source, terms version/date, attribution, changes |
| `sidecar_locator` | string/null | Relative safe path only when retained |
| `sidecar_sha256` | string/null | Required and equal to response digest when retained |

### SourceDocumentEvidence

Parsed identity and revision of one source market document.

| Field | Type | Rules |
| --- | --- | --- |
| `document_ref` | string | Artifact-local reference |
| `response_id` | string | Source response containing the document |
| `namespace_uri` | string | Validated ENTSO-E schema family |
| `root_document_type` | string | Valid data root; acknowledgement roots fail acquisition |
| `document_mrid` | string | Non-empty source identity |
| `revision_number` | integer | Non-negative source revision |
| `created_at_utc` | aware instant | Source document timestamp |
| `document_type` | enum | `A44`, `A81`, or `A89` |
| `process_type` | string/null | Source-returned process; A44 may omit it, while A81/A89 require `A34` |
| `business_type` | string/null | `A95` for required FCR series |
| `flow_direction` | string/null | `A03` for required symmetric FCR |
| `area_eic` | string | Must match France profile |
| `market_agreement_type` | string/null | Preserved and validated for reserve product |
| `product_identity` | object | Tender/product/horizon fields needed to match A81/A89 |
| `document_period` | `CanonicalInterval` | Source-declared coverage |
| `status` | enum | `selected` or `superseded` |

The comparable refresh revision key is the tuple of source name, endpoint
identity, document type, document mRID, semantic series identity, and covered
period. Revision values from different keys are not ordered together.

### CanonicalInterval

Reusable, unambiguous delivery interval.

| Field | Type | Rules |
| --- | --- | --- |
| `start_utc` / `end_utc` | ISO UTC instant | Strictly increasing |
| `local_start` / `local_end` | ISO local instant | Explicit offset |
| `start_utc_offset_seconds` / `end_utc_offset_seconds` | integer | Must agree with `Europe/Paris` conversion |
| `start_fold` / `end_fold` | integer | 0 or 1; repeated local time is explicit |
| `market_timezone` | string | `Europe/Paris` |
| `interval_convention` | string | `start-inclusive/end-exclusive` |

### MarketObservation

One normalized value over one canonical interval.

| Field | Type | Rules |
| --- | --- | --- |
| `interval` | `CanonicalInterval` | No gap/overlap in its canonical series |
| `value` | finite number | Negative allowed only where the series permits it |
| `document_ref` | string | Selected source document evidence |
| `source_position` | integer/null | Preserved XML point position |
| `conversion_ref` | string/null | Required when source and canonical units/resolutions differ |

### MarketSeries

One complete required series.

| Field | Type | Rules |
| --- | --- | --- |
| `series_id` | enum | `day_ahead_price`, `fcr_contracted_volume`, `fcr_capacity_price` |
| `semantic_version` | string | Version of product meaning |
| `area_eic` | string | France only |
| `source_document_type` | enum | Exact A44/A81/A89 mapping |
| `source_resolution` | ISO duration/list | Preserved from source documents |
| `canonical_resolution` | ISO duration | `PT1H` for energy; `PT4H` for FCR profile |
| `source_unit` | string | Exact source unit/settlement basis |
| `canonical_unit` | string | `EUR/MWh`, `MW`, or `EUR/MW/h` |
| `currency` | string/null | `EUR` for price series |
| `conversion` | object/null | Formula, factor, and evidence if converted |
| `observations` | ordered list | Complete, unique UTC coverage |
| `diagnostics` | object | Exact duplicates collapsed, superseded revisions, conversions |

Negative day-ahead prices are valid. Reserve volume must be non-negative. FCR
price must satisfy the validated source profile; no sign correction is inferred.

### MarketDataArtifact

Immutable source-independent artifact consumed by the simulator.

| Field | Type | Rules |
| --- | --- | --- |
| `schema_version` | string | `oel.market-data.v1` |
| `artifact_id` | string | Token-free immutable ID |
| `profile_id` | string | France day-ahead plus symmetric FCR v1 |
| `normalization_version` | string | Required |
| `created_at_utc` | aware instant | Publication provenance |
| `requested_period` | UTC interval | Exact caller request |
| `actual_covered_period` | UTC interval | Full normalized intervals preserved |
| `area` | object | France EIC, name, timezone |
| `series` | map | Exactly one of every required `MarketSeries` |
| `query_windows` | list | Sanitized semantic request windows |
| `raw_responses` | list | Digest and retention evidence for every response |
| `source_documents` | list | Selected and superseded revision evidence |
| `content_fingerprint` | SHA-256 | Stable normalized-content comparison hash |
| `artifact_fingerprint` | SHA-256 | Full manifest integrity hash |
| `predecessor_artifact_fingerprint` | SHA-256/null | Immutable refresh lineage |
| `retention_and_license` | object | Attribution and normalized-fixture reuse terms |

`content_fingerprint` excludes artifact identity, retrieval/publication times,
lineage, and sidecar locator. `artifact_fingerprint` covers all manifest fields
except itself. The canonical serialization uses UTF-8 JSON, sorted keys,
compact separators for hashing, stable list order, and rejects NaN/infinity.

### MarketDataFetchResult

| Field | Type | Meaning |
| --- | --- | --- |
| `outcome` | enum | `published` |
| `artifact` | `MarketDataArtifact` | Fully loaded published artifact |
| `artifact_path` | path | Token-free final path |
| `attempt_diagnostics` | list | Sanitized summaries only |

There is no partial-success outcome.

### MarketDataRefreshResult

| Field | Type | Meaning |
| --- | --- | --- |
| `outcome` | enum | `unchanged`, `published`, or `revision_regression` |
| `current_artifact_fingerprint` | SHA-256 | Input lineage identity |
| `returned_content_fingerprint` | SHA-256/null | Available after validation |
| `new_artifact` / `new_artifact_path` | optional | Present only for `published` |
| `diagnostics` | list | Includes comparable revision values on rejection |

An unchanged or rejected refresh writes no new manifest and never mutates the
current artifact.

## Activation Entities

### ActivationImportRequest

| Field | Type | Rules |
| --- | --- | --- |
| `source_name` / `source_locator` | string | Explicit provenance |
| `source_revision` | string | Dataset release, file digest, or repository commit |
| `source_timezone` | string | Required if source timestamps lack offsets |
| `requested_period` | UTC interval | Exact desired coverage |
| `source_resolution` | ISO duration | Required |
| `source_value_kind` | enum | `interval_average` or `instantaneous_left_hold` |
| `source_sign_meaning` | string | Explicit |
| `normalization_rule` | object | Formula, parameters, clipping, target sign |
| `redistribution_basis` | object | Terms and attribution |

### ActivationSample

| Field | Type | Rules |
| --- | --- | --- |
| `interval` | `CanonicalInterval` | Exactly one activation resolution |
| `activation` | finite number | Inclusive `[-1, 1]` |
| `source_value` | finite number/null | Optional audit value when redistribution permits |
| `source_unit` | string | `Hz` for selected RTE input |
| `conversion_ref` | string | Required unless already canonical |

### RegulationActivationTrace

| Field | Type | Rules |
| --- | --- | --- |
| `schema_version` | string | `oel.regulation-activation.v1` |
| `trace_id` | string | Immutable ID |
| `created_at_utc` | aware instant | Import provenance |
| `covered_period` | UTC interval | Exact contiguous sample coverage |
| `resolution` | ISO duration | `PT10S` for reference fixture |
| `value_semantics` | string | Interval-average normalized FCR activation |
| `sign_semantics` | string | Positive is upward/discharge |
| `source` | object | Name, locator, revision, timezone, raw digest |
| `normalization` | object | Formula and point-to-interval conversion |
| `samples` | ordered list | No gap, duplicate, or overlap |
| `content_fingerprint` | SHA-256 | Stable semantic/sample hash |
| `artifact_fingerprint` | SHA-256 | Full manifest integrity hash |
| `retention_and_license` | object | Attribution/reuse basis |

The selected RTE conversion is
`clip((50.0 - frequency_hz) / 0.2, -1, 1)` followed by explicit
left-hold assignment to `[timestamp, timestamp + 10 seconds)`.

## Schedule And Replay Entities

### EnergyBaselineInterval

| Field | Type | Rules |
| --- | --- | --- |
| `interval` | UTC/local interval | Complete hourly block in reference profile |
| `power_kw` | finite number | Positive charge, negative discharge |
| `schedule_source` | enum | `fixed`, `arbitrage_only`, or `stacked_heuristic` |

### EnergyBaselineSchedule

Ordered hourly `EnergyBaselineInterval` values with a schedule ID, semantics
version, covered period, and fingerprint. It is an accepted fixed schedule,
not realized battery power and not an optimization decision.

### FCRCommitmentInterval

| Field | Type | Rules |
| --- | --- | --- |
| `interval` | UTC/local interval | Complete eligible four-hour product block |
| `capacity_kw` | finite number | Non-negative |
| `volume_observation_ref` | string | Compatible A81 interval |
| `price_observation_ref` | string | Compatible A89 interval |

### FCRCapacitySchedule

Ordered four-hour commitments with schedule ID, symmetric product identity,
covered period, and fingerprint. Every block must match an artifact volume and
price and satisfy `capacity_kw / 1000 <= volume_mw`.

### MultiRateTimeContract

| Field | Reference value | Rule |
| --- | --- | --- |
| `energy_resolution` | `PT1H` | Complete schedule blocks |
| `state_checkpoint_resolution` | `PT15M` | Exact grouping of activation intervals |
| `fcr_resolution` | `PT4H` | Complete product blocks |
| `activation_resolution` | `PT10S` | Physical integration step |
| `timezone` | `Europe/Paris` | Delivery labels |
| `interval_convention` | half-open | Same for every grid |

Each finer resolution must divide the next coarser interval exactly in UTC for
the selected replay horizon. Every activation sample maps to exactly one
energy interval, one checkpoint interval, and one FCR block.

### FCRPenaltyRule

| Field | Type | Rules |
| --- | --- | --- |
| `rule_id` | string | Versioned deterministic identity |
| `measure` | enum | `absolute_fcr_non_delivery_energy_kwh` |
| `rate` | finite number | Non-negative |
| `rate_unit` | string | `EUR/kWh` |
| `application` | string | Sum per activation interval |

The absence of this entity means zero penalty. No implicit default market
penalty exists.

### TerminalSOCTarget

Optional report-only target with stored-energy kWh or SOC fraction, target
value, and tolerance. It cannot be read by the dispatch loop.

### StackedServiceReplayRequest

| Field | Type | Rules |
| --- | --- | --- |
| `market_artifact` | artifact/fingerprint | Valid and covers replay |
| `activation_trace` | artifact/fingerprint | Valid and exact coverage |
| `battery` | existing `BatteryComponent` | One battery only |
| `energy_schedule` | `EnergyBaselineSchedule` | Fixed and complete |
| `fcr_schedule` | `FCRCapacitySchedule` | Fixed and complete |
| `time_contract` | `MultiRateTimeContract` | Exact mappings |
| `penalty_rule` | optional | Explicit if nonzero penalty desired |
| `terminal_soc_target` | optional | Report only |
| `numeric_tolerance` | number | Default `1e-6`, positive |
| `simulation_semantics_version` | string | Required fingerprint input |

### ReplaySample

One activation-substep audit record.

| Field | Unit | Definition |
| --- | --- | --- |
| `interval` | time | Activation interval |
| `energy_interval_ref` / `fcr_interval_ref` | ID | Exact coarser mappings |
| `baseline_power_kw` | kW | Accepted fixed energy baseline |
| `fcr_capacity_kw` | kW | Fixed symmetric commitment |
| `activation` | 1 | Canonical interval average |
| `requested_fcr_power_kw` | kW | `-activation * fcr_capacity_kw` |
| `requested_combined_power_kw` | kW | Baseline plus requested FCR |
| `delivered_combined_power_kw` | kW | Battery-constrained delivery |
| `delivered_fcr_power_kw` | kW | Delivered combined minus baseline when FCR nonzero; otherwise zero |
| `baseline_delivery_error_kw` | kW | Separate zero-FCR/diagnostic baseline shortfall |
| `signed_tracking_error_kw` | kW | Requested FCR minus delivered FCR |
| `absolute_tracking_error_kw` | kW | Absolute signed error |
| `non_delivery_energy_kwh` | kWh | Absolute tracking error times duration |
| `charge_energy_kwh` / `discharge_energy_kwh` | kWh | Battery-terminal movement |
| `stored_energy_before_kwh` / `stored_energy_after_kwh` | kWh | SOC audit |
| `saturation_causes` | list | Ordered subset of charge power, discharge power, min SOC, max SOC |

For zero FCR, all FCR response/tracking/non-delivery fields are exactly zero.

### SaturationEvent

Contiguous one-cause interval aggregate with event ID, cause, start/end,
sample count, duration, maximum power error, and undelivered energy. Event order
is chronological, then by fixed cause order.

### SettlementBreakdown

| Field | Unit | Meaning |
| --- | --- | --- |
| `day_ahead_energy_revenue_eur` | EUR | Accepted baseline schedule settlement |
| `fcr_capacity_revenue_eur` | EUR | Eligible committed capacity settlement |
| `penalty_eur` | EUR | Explicit rule only |
| `total_profit_eur` | EUR | Energy + FCR - penalty |
| `activation_energy_settlement_status` | enum | `not_modeled` |
| `imbalance_settlement_status` | enum | `not_modeled` |
| `degradation_cost_status` | enum | `not_modeled` |

Per-energy-interval and per-FCR-block components accompany the totals.

### StackedServiceReplayResult

| Field | Type | Rules |
| --- | --- | --- |
| `simulation_semantics_version` | string | Matches request |
| `input_fingerprints` | object | Market, activation, schedules, config |
| `samples` | ordered list | One per activation interval |
| `state_checkpoints` | ordered list | Initial plus each 15-minute boundary |
| `saturation_events` | ordered list | Deterministic ordering |
| `tracking_summary` | object | Signed/absolute error, non-delivery, counts/durations |
| `throughput_kwh` | finite number | Sum terminal charge + discharge energy |
| `settlement` | `SettlementBreakdown` | Exact reconciliation |
| `terminal_soc_report` | object/null | Target, realized, deviation, compliance |
| `trace_fingerprint` | SHA-256 | Deterministic ordered physical/result trace |
| `result_fingerprint` | SHA-256 | Inputs, trace fingerprint, aggregates, settlement |

## Deterministic Baseline Entities

### RegulationOnlyBaselineConfig

Contains a fixed FCR capacity schedule and battery bounds/efficiencies. It
produces zero energy power in every interval and the centered initial energy:

```text
y_center = (y_max + eta_charge * eta_discharge * y_min)
           / (1 + eta_charge * eta_discharge)
```

It has no recovery rule and does not consume activation values during schedule
construction.

### StackedHeuristicConfig

Contains the existing `PriceThresholdConfig` identity plus an FCR schedule.
For every energy interval it obtains the existing controller request and clips
it to:

```text
[-max_discharge_kw + reserve_kw, max_charge_kw - reserve_kw]
```

An empty admissible interval fails. Future activation is not an input.

## Lifecycle And State Transitions

### Fetch

```text
request + secret
  -> source windows
  -> in-memory raw bytes and digests
  -> parsed documents
  -> normalized series
  -> complete artifact validation
  -> temporary sidecars (if permitted)
  -> temporary manifest
  -> atomic published manifest
```

Any error before the final transition leaves no published artifact.

### Refresh

```text
current immutable artifact + request + secret
  -> fetch and validate candidate in memory
  -> matching revision regression? reject, write nothing
  -> same content fingerprint? unchanged, write nothing
  -> changed content? link predecessor and atomically publish new artifact
```

### Offline Replay

```text
load + integrity validation
  -> schedule/market/headroom validation
  -> activation/grid validation
  -> physical replay
  -> settlement and reports
  -> deterministic fingerprints
```

No transition in this lifecycle has access to a network transport.
