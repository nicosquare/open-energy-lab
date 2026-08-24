# Data Model: BESS aFRR and mFRR Services

**Feature**: `011-afrr-mfrr-services`  
**Schema family**: `oel.restoration.*.v1`  
**Default numeric tolerance**: `1e-6`

## Conventions

- All computation intervals are start-inclusive/end-exclusive and authoritative
  in UTC. Europe/Paris labels, UTC offsets, and fold/gap identity are retained
  as metadata through the existing `CanonicalInterval` type.
- Positive battery power is charge. Negative battery power is discharge.
- `upward` restoration therefore maps to negative balancing power; `downward`
  maps to positive balancing power.
- Power is kW, battery-terminal energy is kWh, area power/volume is preserved in
  the source unit (normally MW), and activation prices are EUR/MWh unless the
  source series explicitly declares another unit.
- All public models are frozen/slotted dataclasses with finite values, tuples,
  and immutable mappings. Canonical JSON rejects NaN and infinity.
- Every persisted or replayable object has an explicit schema/semantics version
  and deterministic SHA-256 fingerprint.
- `None`, source null, field absence, and numeric zero are not synonyms.

## Shared Enumerations

### RestorationProduct

Values: `AFRR`, `MFRR`. FCR is deliberately absent from Feature 011 input
types; Feature 010 owns FCR.

### RestorationDirection

Values: `UPWARD`, `DOWNWARD`.

### MFRRActivationKind

Values: `SCHEDULED`, `DIRECT`. Exact kind is mandatory for every event.

### ObservationValueState

Values:

- `VALUE`: a finite numeric value was present; zero remains `VALUE`
- `SOURCE_NULL`: the named field was present with JSON null
- `FIELD_ABSENT`: the named field did not occur in the source row

### SeriesAvailability

Values:

- `PRESENT`: required coverage contains numeric observations
- `PRESENT_WITH_NULLS`: the series exists but one or more covered values are
  explicit source nulls
- `SOURCE_ABSENT`: the requested source field/series does not exist for the
  response/profile
- `NOT_REQUESTED`: the request did not select the series

### SettlementAvailability

Values: `AVAILABLE`, `UNAVAILABLE`. There is no partially available total.

## Market Acquisition Entities

### RTERestorationProfile

Closed source profile for one RTE resource.

| Field | Type | Rule |
|---|---|---|
| `profile_id` | string | `fr-rte-balancing-energy-v5.2-afrr-v1` or `...-mfrr-v1` |
| `catalog_version` | string | exactly `5.2` |
| `api_path_version` | string | exactly `v5` |
| `source_name` | string | RTE Balancing Energy |
| `resource` | string | `standard_afrr_data` or `standard_mfrr_data` |
| `root_field` | string | `picasso` or `mari`, consistent with resource |
| `rows_field` | string | `picasso_mesures` or `mari_mesures` |
| `area` | string | France control/scheduling area identity |
| `market_timezone` | string | `Europe/Paris` |
| `expected_resolution` | string | `PT15M` |
| `series_contract` | tuple | exact requested/required/optional semantic IDs |

Cross-resource construction is rejected.

### RestorationMarketDataRequest

Credential-free description of one explicit `fetch` or `refresh` source
operation.

| Field | Type | Rule |
|---|---|---|
| `source` | enum | `RTE` or `ENTSOE`; one source only |
| `profile_id` | string | registered closed profile |
| `resource_identity` | string | RTE resource or ENTSO-E document profile |
| `source_endpoint` | HTTPS URL | origin/path only; no user info/query/fragment |
| `requested_start_utc` | datetime | aware UTC, 15-minute aligned for RTE |
| `requested_end_utc` | datetime | aware UTC and later than start |
| `requested_series_ids` | tuple[string] | non-empty, unique, profile-known |
| `required_series_ids` | tuple[string] | subset of requested series |
| `normalization_version` | string | non-empty |
| `raw_retention_policy` | enum | `DIGEST_ONLY` or `PERMITTED_SIDECAR` |
| `mode` | enum | `FETCH` or `REFRESH` only |

The request has a deterministic identity excluding credentials, tokens,
retrieval time, response revision, and output path. Offline loading accepts an
artifact path/identity instead of this source request.

### RTEOAuthSession

Ephemeral operation-local value; never serialized or fingerprinted.

| Field | Type | Rule |
|---|---|---|
| `access_token` | secret string | memory only; never represented in repr/errors |
| `obtained_at` | monotonic/UTC time | runtime use only |
| `expires_at` | optional runtime time | controls in-operation renewal only |

Client ID and client secret are function arguments at the explicit acquisition
boundary, not fields on this entity or any request/artifact.

### SourceRequestEvidence

Sanitized record for one market-resource query window.

| Field | Type | Rule |
|---|---|---|
| `request_id` | string | deterministic token-free identity |
| `resource` | string | exact source resource/document |
| `start_utc`, `end_utc` | timestamp | exact attempted half-open window |
| `attempt_count` | int | 1..3 |
| `http_status_class` | string | sanitized outcome, not headers/body |
| `response_media_type` | string | validated allowed type |
| `response_bytes` | int | non-negative and within configured maximum |
| `raw_sha256` | string | digest of market response bytes only |
| `source_revision` | optional string | when provided by source |

OAuth responses and Authorization headers are never source evidence.

### RestorationMarketObservation

| Field | Type | Rule |
|---|---|---|
| `interval` | `CanonicalInterval` | within requested and covered period |
| `value_state` | `ObservationValueState` | mandatory |
| `value` | optional float | finite iff state is `VALUE` |
| `source_row` | int | deterministic original row index |
| `source_field` | string | exact JSON/XML field identity |
| `document_ref` | string | references acquisition evidence |
| `conversion_ref` | optional string | required when unit/sign/time conversion occurred |

Rows with the same series and interval may not conflict. Source order may be
normalized chronologically, while `source_row` preserves evidence ordering.

### RestorationMarketSeries

One independently provenanced semantic series.

| Field | Type | Rule |
|---|---|---|
| `series_id` | string | unique within artifact |
| `semantic_version` | string | explicit and supported |
| `source`, `source_version` | string | exact owner/interface version |
| `resource`, `source_field` | string | exact origin |
| `product`, `process`, `direction` | typed optional values | never inferred when required |
| `area` | string | source control/market area |
| `requested_period`, `covered_period` | interval | covered must satisfy required contract |
| `source_resolution`, `canonical_resolution` | duration | PT15M for RTE reference profiles |
| `source_unit`, `canonical_unit` | string | explicit |
| `currency` | optional string | required for monetary values |
| `availability` | `SeriesAvailability` | explicit |
| `transformations` | tuple | ordered and reproducible |
| `observations` | tuple | ordered, non-overlapping |
| `series_fingerprint` | SHA-256 | normalized semantic content |

Requested required series cannot finish as `SOURCE_ABSENT` or with coverage
gaps. Optional sparse fields may do so and remain inspectable.

### RestorationMarketArtifact

Immutable output from exactly one source acquisition.

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | `oel.restoration.market.v1` |
| `artifact_id` | string | stable request/profile identity |
| `source` | enum | exactly one source |
| `source_version`, `profile_id`, `resource` | string | exact |
| `request_identity` | SHA-256 | token-free request identity |
| `requested_period`, `covered_period` | interval | canonical UTC/local identity |
| `retrieved_at_utc` | timestamp | provenance only |
| `series_manifest` | mapping | requested/present/absent/required states |
| `series` | tuple | all from same acquisition/source |
| `request_evidence` | tuple | complete market-resource windows |
| `raw_retention` | mapping | digest/sidecar policy and status |
| `redistribution_policy` | mapping | owner, attribution, repository/release rules |
| `predecessor_artifact_fingerprint` | optional SHA-256 | changed refresh only |
| `content_fingerprint` | SHA-256 | normalized market content excluding retrieval/lineage |
| `artifact_fingerprint` | SHA-256 | full immutable manifest identity |

The filename contains `artifact_fingerprint`. Existing non-identical bytes at
that filename are an integrity failure. A valid identical file may be reused.

### RestorationStudyBundleRef

| Field | Type | Rule |
|---|---|---|
| `artifact_id` | string | referenced acquisition identity |
| `artifact_fingerprint` | SHA-256 | exact immutable version |
| `selected_series_ids` | tuple[string] | must exist in referenced artifact |
| `purpose` | string | why the study uses these series |

### RestorationStudyBundle

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | `oel.restoration.study-bundle.v1` |
| `bundle_id` | string | non-empty |
| `study_period` | interval | all selected series must cover their declared use |
| `references` | tuple[`RestorationStudyBundleRef`] | non-empty, unique artifacts |
| `redistribution_policy` | mapping | at least as restrictive as every reference |
| `bundle_fingerprint` | SHA-256 | references, selections, period, purpose |

The bundle stores no `RestorationMarketObservation` and performs no join,
rename, interpolation, or source substitution.

## Derived Activation Entities

### DerivedSimulationMapping

| Field | Type | Rule |
|---|---|---|
| `mapping_id` | string | unique |
| `source_artifact_fingerprint` | SHA-256 | exact source version |
| `source_series_fingerprints` | tuple[SHA-256] | requested input series only |
| `product`, `direction` | typed identity | exact |
| `asset_allocation_fraction` | float | finite in `[0,1]`, fixed |
| `unit_scale_kw_per_mw` | float | exactly `1000` for RTE MW mapping |
| `capacity_commitment_ref` | SHA-256 | target directional commitment |
| `driver_semantics` | string | aFRR requested need or mFRR SA requested volume |
| `comparison_series` | tuple[SHA-256] | activated/satisfied context, never drivers |
| `assumptions` | tuple[string] | explicit and non-empty |
| `created_at_utc` | timestamp | provenance only |
| `output_label` | string | exactly `derived_simulation` |
| `mapping_fingerprint` | SHA-256 | all semantic inputs |

Formula: `area_requested_MW * 1000 * fraction`. The builder rejects any
capacity excess, simultaneous opposing aFRR need, missing source value, hidden
clipping, or time-varying fraction.

### AFRRActivationSample

| Field | Type | Rule |
|---|---|---|
| `interval` | `CanonicalInterval` | complete trajectory grid |
| `requested_balancing_power_kw` | float | finite; charge-positive signed power |
| `direction` | optional direction | null only when power is exactly zero |
| `source_observation_refs` | tuple | exact lineage |

Each value is the interval-average requested power and integrates as
`power_kw * interval_hours`.

### AFRRActivationTrajectory

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | `oel.restoration.afrr-trajectory.v1` |
| `product` | enum | exactly `AFRR` |
| `period` | interval | exactly covered by samples |
| `resolution` | duration | fixed within a trajectory |
| `sample_semantics` | string | `interval_average_requested_bess_power_kw` |
| `sign_convention` | string | charge-positive |
| `source_kind` | enum | `ASSET_SUPPLIED`, `SYNTHETIC`, `DERIVED_SIMULATION` |
| `created_or_retrieved_at_utc` | timestamp | explicit provenance time included in identity |
| `mapping_fingerprint` | optional SHA-256 | required iff derived |
| `samples` | tuple | gap-free, non-overlapping, chronological |
| `trajectory_fingerprint` | SHA-256 | all semantic content, including provenance time |

Interpolation and upsampling are not operations on this type.

### MFRRActivationEvent

| Field | Type | Rule |
|---|---|---|
| `event_id` | string | unique in sequence |
| `kind` | enum | `SCHEDULED` or `DIRECT` |
| `direction` | enum | explicit |
| `requested_start_utc` | timestamp | aware UTC within horizon |
| `activation_delay_seconds` | float | finite, non-negative |
| `ramp_up_seconds` | float | finite, non-negative |
| `hold_seconds` | float | finite, non-negative |
| `ramp_down_seconds` | float | finite, non-negative |
| `requested_power_kw` | float | finite, non-negative magnitude |
| `source_kind` | enum | asset/synthetic/derived |
| `mapping_fingerprint` | optional SHA-256 | required iff derived |
| `event_fingerprint` | SHA-256 | complete event identity |

Total event duration must be positive. Requested energy is
`requested_power_kw * (hold + 0.5*ramp_up + 0.5*ramp_down) / 3600`.
Direction applies sign after magnitude validation. The full event interval
includes delay, both ramps, and hold.

### MFRRActivationSequence

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | `oel.restoration.mfrr-events.v1` |
| `product` | enum | exactly `MFRR` |
| `period` | interval | contains every complete event interval |
| `events` | tuple | ordered by start then event ID; no overlap |
| `sequence_fingerprint` | SHA-256 | all events and semantics |

SA and DA events remain distinct even when their numeric shapes match.

## Control Entities

### DirectionalCapacityCommitmentInterval

| Field | Type | Rule |
|---|---|---|
| `interval` | `CanonicalInterval` | product delivery interval |
| `product` | enum | AFRR or MFRR |
| `direction` | enum | upward/downward |
| `committed_capacity_kw` | float | finite, non-negative |
| `eligibility` | bool | explicit study input |
| `source_or_assumption_ref` | string | traceable |

### DirectionalCapacitySchedule

Contains one product's complete, non-overlapping upward and downward
commitments over the replay horizon, plus semantics version and fingerprint.
Missing direction is represented by an explicit zero commitment, not by using
the other direction.

### RestorationEnergyBaselineInterval

Contains one canonical interval and accepted charge-positive baseline kW. The
new type avoids the Feature 010 builder's FCR-specific grid and source enum.

### RestorationEnergyBaselineSchedule

Complete, gap-free baseline for the replay period with source/configuration
identity and fingerprint. It has no activation input or activation-derived
field.

### RestorationCapability

| Field | Type | Rule |
|---|---|---|
| `max_ramp_up_kw_per_second` | float | finite, positive |
| `max_ramp_down_kw_per_second` | float | finite, positive |
| `max_activation_delay_seconds` | mapping[product, float] | finite, non-negative |
| `min_supported_duration_seconds` | mapping[product, float] | finite, non-negative |
| `max_supported_duration_seconds` | mapping[product, float] | finite, positive and >= min |

This service capability is separate from stable `BatteryComponent` power, SOC,
and efficiency fields.

### RestorationBaselineConfig

Discriminated configs support fixed caller-supplied baselines and deterministic
product-specific heuristics. Every config includes product, commitments,
battery, capability, period/grid, parameters, tolerance, and fingerprint. It
never contains a trajectory or event sequence.

## Replay Entities

### AFRRReplayRequest

Exact fields: battery, restoration capability, initial state, aFRR directional
schedule, restoration energy baseline, `AFRRActivationTrajectory`, replay
integration grid, optional settlement/degradation rules, semantics version,
tolerance, and all input fingerprints. Exact runtime type checks reject mFRR
events and FCR traces.

### MFRRReplayRequest

Same shared physical inputs, but requires one mFRR directional schedule and one
`MFRRActivationSequence`. Exact runtime type checks reject aFRR/FCR inputs.

### RestorationReplaySample

| Field group | Required fields |
|---|---|
| Identity/time | sample index, interval, product, optional mFRR event/kind |
| Baseline/request | accepted baseline, requested balancing, requested combined power |
| Capability | capability-accepted combined/balancing power, ramp, response delay |
| Delivery | delivered combined and balancing power, charge/discharge/net energy |
| Performance | signed/absolute tracking error, delivered/undelivered activation energy |
| State | SOC, stored energy, upward/downward power and energy headroom |
| Diagnostics | ordered saturation/non-performance causes and duration |

### MFRREventPerformance

Aggregates one event's requested/actual start and completion, kind/direction,
requested/delivered/undelivered energy, achieved ramps, delays, saturation
durations, and deterministic causes. It references the event fingerprint.

### AFRRReplayResult

Contains validated request identity, chronological samples, interval and
directional aggregates, physical totals, throughput, performance summary,
input fingerprints, diagnostics, and result fingerprint. It has no mFRR event
collection.

### MFRRReplayResult

Contains the corresponding sample trace plus `MFRREventPerformance` objects and
aggregate SA/DA/directional totals. It has no aFRR tracking-trajectory field.

## Settlement Entities

### DirectionalCapacityPrice

Product, direction, covered interval, finite price, unit, currency, source or
assumption reference, eligibility rule, and fingerprint.

### DirectionalActivationPrice

Product, direction, covered interval, finite price, unit/currency, and pricing
basis. When sourced from an RTE area series, it additionally requires an
`AreaPriceProxyMapping` and label `scenario_proxy`.

### AreaPriceProxyMapping

References source artifact/series fingerprint, product, direction, price field,
coverage, transformation, assumptions, and output label. It cannot use an
incompatible/missing price or claim `asset_invoice`.

### RestorationPenaltyRule

Product, event/period basis, direction applicability, measured shortfall,
non-negative price/rate, unit, application interval, and fingerprint. Absence
means zero penalty with status `UNCONFIGURED`, not an inferred market rule.

### ThroughputDegradationRule

Optional finite non-negative cost per kWh of battery-terminal throughput. Its
description must state that it is a comparison proxy, not an electrochemical
aging model. Absence means zero cost with status `UNCONFIGURED`.

### RestorationSettlement

| Field | Rule |
|---|---|
| `availability` | `AVAILABLE` only if every declared required price/rule input is compatible and covered |
| `unavailable_reasons` | non-empty only when unavailable; identifies source/field/period/expected condition |
| `day_ahead_energy_revenue` | accepted baseline only |
| `upward_capacity_revenue`, `downward_capacity_revenue` | eligible directional commitments only |
| `upward_activation_revenue`, `downward_activation_revenue` | eligible delivered activation energy only |
| `non_performance_penalty` | explicit rule, or zero/unconfigured |
| `throughput_kwh`, `degradation_cost` | absolute terminal charge+discharge and explicit proxy |
| `gross_revenue`, `net_result` | present only when available |
| `price_mapping_labels` | preserves assumption/proxy identity |
| `settlement_fingerprint` | rules, prices, replay result, components/status |

When available:

`net = day_ahead + upward_capacity + downward_capacity + upward_activation + downward_activation - penalty - degradation`

The unselected restoration product has no component fields.

## Diagnostic Entity

### RestorationDiagnostic

Fields: stable code, phase (`request`, `auth`, `transport`, `parse`, `artifact`,
`mapping`, `commitment`, `replay`, `settlement`, `distribution`), source,
resource/field, requested period, observed sanitized condition, expected
condition, product/direction/event when relevant, attempt count, and public
message. It has no credential/header/full request URL/raw body field.

## Relationships

```text
RestorationMarketDataRequest
  -> SourceRequestEvidence
  -> RestorationMarketArtifact
       -> RestorationMarketSeries
            -> RestorationMarketObservation

RestorationMarketArtifact(s)
  <- RestorationStudyBundle (fingerprint references only)

RestorationMarketSeries + DirectionalCapacitySchedule
  -> DerivedSimulationMapping
       -> AFRRActivationTrajectory OR MFRRActivationSequence

RestorationEnergyBaselineSchedule
DirectionalCapacitySchedule
BatteryComponent + RestorationCapability
AFRRActivationTrajectory OR MFRRActivationSequence
  -> matching ReplayRequest
       -> matching ReplayResult
            -> RestorationSettlement
```

## Lifecycle and State Transitions

### Fetch

```text
token-free request validated
  -> credentials read by explicit caller operation
  -> ephemeral OAuth token obtained
  -> market resource requested (1..3 attempts)
  -> complete response parsed in memory
  -> all required series/coverage/semantics validated
  -> canonical fingerprints computed
  -> immutable artifact published atomically
```

Any failure before publication produces no complete artifact.

### Refresh

```text
current artifact loaded and verified
  -> request identity compatibility checked
  -> explicit source acquisition and normalization
  -> compare content fingerprint
       unchanged -> report UNCHANGED; write nothing
       changed   -> link predecessor; publish one successor
       failure   -> preserve current artifact; publish nothing
```

### Offline Load

```text
path selected -> bytes/schema/fingerprint/sidecar/policy validated -> artifact
```

No environment, OAuth, adapter construction, or network call is permitted.

### Derived Scenario

```text
artifact/series/commitment verified
  -> fixed fraction and driver semantics validated
  -> every mapped request calculated without clipping
  -> ambiguity/capacity checks
  -> immutable derived activation artifact
```

### Replay and Settlement

```text
exact product types + full coverage validated
  -> commitment/baseline feasibility checked
  -> deterministic physical replay
  -> immutable physical result
  -> settlement inputs checked
       complete/compatible -> AVAILABLE settlement and total
       missing/ambiguous   -> UNAVAILABLE settlement; physical result retained
```
