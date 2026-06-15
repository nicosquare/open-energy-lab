# Data Model: Stochastic Weather Generation And Simulator Integration

This feature introduces a public weather capability under
`open_energy_lab.weather` and a simulator-side stochastic scenario-family
surface under `open_energy_lab.simulator`.

## Canonical Weather Dataset

**Fields**: `dataset_id`, `latitude`, `longitude`, `source_name`,
`source_metadata`, `timezone_name`, `time_basis`, `timestep_hours`,
`timestamp_utc`, `local_civil_step_labels`, `canonical_field_order`,
`field_series`.

**Relationships**: Produced by the library-owned TMY fetch and normalization
workflow; consumed by the fit workflow to produce one persisted fitted weather
artifact.

**Validation rules**:

- `time_basis` is fixed to location-local civil time for fitting semantics.
- `timestamp_utc` remains present as part of the canonical public schema.
- `field_series` must include all ten canonical first-release weather fields.
- every field series length must align to one common timestep and one common
  normalized annual record.
- missing or unmappable required fields fail the workflow rather than creating
  a partial dataset.

## Fitted Weather Model Artifact

**Fields**: `artifact_id`, `schema_version`, `feature_name`, `created_at`,
`latitude`, `longitude`, `timezone_name`, `time_basis`, `timestep_hours`,
`canonical_field_order`, `training_record_summary`, `base_model_kind`,
`base_model_parameters`, `cloud_event_model`, `provenance`, `supported_load_modes`.

**Relationships**: Produced from one canonical weather dataset; loaded later by
  the offline sampling workflow; referenced by scenario-family requests.

**Validation rules**:

- `schema_version` must be explicitly supported or loading fails fast.
- `timestep_hours` is part of the stable contract and locks future sampling to
  the same resolution.
- `canonical_field_order` must match the first-release canonical schema exactly.
- artifact contents must be sufficient to sample without network access or
  refitting.

## Joint Weather Model Parameters

**Fields**: `intervals_per_day`, `field_order`, `mean_vector`,
`covariance_matrix`, `regularization_note`, `training_day_count`,
`physical_bounds_policy`.

**Relationships**: Embedded inside one fitted weather model artifact; consumed
  by the sampler to produce base daily weather blocks before cloud-event
  overlays are applied.

**Validation rules**:

- `field_order` must align with the artifact's canonical field order.
- `mean_vector` and `covariance_matrix` dimensions must match
  `intervals_per_day * len(field_order)`.
- `physical_bounds_policy` must document non-negative or bounded clipping rules
  for fields such as irradiance, humidity, wind speed, and pressure.

## Cloud Event Model

**Fields**: `irradiance_fields`, `start_probability_by_local_step`,
`duration_distribution`, `attenuation_distribution`,
`minimum_base_irradiance_w_per_m2`, `calibration_summary`.

**Relationships**: Embedded inside one fitted weather artifact; applied only to
  irradiance fields after the base joint daily sample is produced.

**Validation rules**:

- `irradiance_fields` must be a subset of the canonical irradiance trio.
- event timing and duration must be defined in local-civil-time step space.
- attenuation magnitudes must preserve non-negative irradiance after overlay.
- the same event interval may affect multiple irradiance fields together.

## Weather Sampling Request

**Fields**: `artifact_id`, `num_steps`, `scenario_count`, `family_seed`,
`requested_summary_fields` (optional), `blackout_configuration` (optional).

**Relationships**: Submitted by a caller after loading a fitted artifact;
  produces one weather scenario family.

**Validation rules**:

- `num_steps` must be positive.
- `scenario_count` must be positive.
- the request timestep is implied by the artifact and cannot override it.
- `family_seed` defines the reproducibility surface for the entire family.

## Sampled Weather Trace

**Fields**: `scenario_index`, `family_seed`, `derived_identity`,
`timestep_hours`, `timestamp_utc`, `canonical_field_series`,
`cloud_event_annotations`.

**Relationships**: Belongs to one weather scenario family; may feed one
  simulator scenario-family evaluation.

**Validation rules**:

- every canonical field series length must equal `num_steps`.
- the same family seed and scenario ordering must reproduce the same trace.
- physical-bounds enforcement applies after cloud-event overlays.
- `cloud_event_annotations` may be empty but must be explicit.

## Blackout Scenario Configuration

**Fields**: `mode`, `intervals`, `source`, `notes`.

**Relationships**: Supplied by the caller alongside or inside one weather
  sampling request; transformed into per-scenario blackout traces for simulator
  evaluation.

**Validation rules**:

- `mode` is fixed to grid-outage-only in the first release.
- blackout intervals must align to the scenario-family timestep.
- blackout configuration is separate from the fitted weather artifact.

## Blackout Disturbance Trace

**Fields**: `scenario_index`, `grid_available`, `interval_annotations`.

**Relationships**: Belongs to one weather scenario family; consumed by the
  simulator integration layer during family evaluation.

**Validation rules**:

- trace length must equal the sampled weather trace length for the same
  scenario index.
- `grid_available` is explicit for every step.
- blackout traces may coexist with cloud events but are never derived from
  irradiance behavior alone.

## Weather Scenario Family

**Fields**: `family_id`, `artifact_reference`, `family_seed`, `scenario_count`,
`num_steps`, `timestep_hours`, `sampled_traces`, `blackout_traces`.

**Relationships**: Produced by the sampling workflow; consumed by one simulator
  family evaluation request.

**Validation rules**:

- every sampled trace and blackout trace must share the same `num_steps` and
  `timestep_hours`.
- scenario indices must be unique within the family.
- blackout traces may be absent only when no blackout configuration is supplied.

## Simulator Family Evaluation Request

**Fields**: `base_scenario_reference`, `weather_family`, `summary_output_fields`,
`numeric_tolerance`.

**Relationships**: Submitted to the simulator-side stochastic family evaluator;
  produces one weather scenario family result.

**Validation rules**:

- the base scenario must preserve deterministic `BatteryLoadPVScenario`
  semantics aside from the substituted weather and blackout inputs.
- `summary_output_fields` must be limited to documented core simulator outputs.
- `numeric_tolerance` defaults to absolute `1e-6`.

## Weather Scenario Family Result

**Fields**: `family_id`, `scenario_results`, `summary_statistics`,
`supported_summary_fields`, `family_seed`, `timestep_hours`.

**Relationships**: Produced from one simulator family evaluation request; may
  feed later visualization or analysis layers.

**Validation rules**:

- `scenario_results` must preserve per-scenario ordering and scenario index.
- `summary_statistics` must include min, mean, max, 5th, 50th, and 95th
  percentiles for documented core simulator outputs only.
- raw weather variables are not part of the stable summary surface.
- repeated evaluation with the same family seed, artifact, and scenario order
  must reproduce both scenario results and summary statistics.

## Scenario Evaluation Result

**Fields**: `scenario_index`, `pv_generation_kw`, `net_grid_power_kw`,
`unmet_load_kw`, `step_settlement`, `total_settlement`, `blackout_active`,
`weather_reference`, `constraint_events`.

**Relationships**: Belongs to one weather scenario family result; mirrors the
  deterministic simulator trace surface while adding outage-aware fields needed
  for grid-outage semantics.

**Validation rules**:

- `unmet_load_kw` is explicit during blackout intervals and zero otherwise.
- `blackout_active` length must align to the scenario timestep count.
- deterministic-path fields retain their existing units and sign conventions.

## Lifecycle Notes

1. Fetch and normalize one canonical weather dataset from geolocation input.
2. Fit one fixed-timestep weather artifact from that dataset.
3. Persist the artifact with supported schema version and provenance.
4. Load the artifact offline and sample one weather scenario family from a
   family seed.
5. Optionally attach caller-configured blackout traces.
6. Evaluate the family against one base simulator configuration and emit
   scenario results plus stable family summaries.
