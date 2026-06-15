# Data Model: Weather-Conditioned Demand Modeling And Simulator Integration

This feature introduces a public demand capability under
`open_energy_lab.demand` and a simulator-side paired weather-and-demand
scenario-family surface under `open_energy_lab.simulator`.

## Aligned Demand Training Dataset

**Fields**: `dataset_id`, `timezone_name`, `timestep_hours`,
`timestamp_utc`, `local_civil_step_labels`, `canonical_weather_fields`,
`weather_field_series`, `non_thermal_electric_demand_kw`,
`cooling_demand_rt`, `provenance`.

**Relationships**: Produced from canonical weather outputs plus explicit
historical demand series; consumed by the fit workflow to produce one
persisted fitted demand artifact.

**Validation rules**:

- `timestamp_utc`, weather fields, non-thermal electric demand, and cooling
  demand must align on one common timestep and horizon.
- the weather inputs must come from the canonical weather contract rather than
  ad hoc field names.
- `non_thermal_electric_demand_kw` and `cooling_demand_rt` must both be
  explicit; the workflow must not infer either from total electric demand.
- all series lengths must match exactly.

## Fitted Demand Model Artifact

**Fields**: `artifact_id`, `schema_version`, `feature_name`, `created_at`,
`timezone_name`, `time_basis`, `timestep_hours`,
`required_weather_field_order`, `training_record_summary`,
`non_thermal_electric_model`, `cooling_demand_model`,
`shared_residual_model`, `double_counting_policy`, `provenance`,
`supported_sampling_modes`.

**Relationships**: Produced from one aligned training dataset; loaded later by
the offline demand sampling workflow; referenced by paired scenario-family
requests.

**Validation rules**:

- `schema_version` must be explicitly supported or loading fails fast.
- `timestep_hours` is part of the stable contract and locks future sampling to
  the same resolution.
- `required_weather_field_order` must be a documented subset of the canonical
  weather schema required by the demand model.
- `double_counting_policy` must state that explicit cooling demand cannot also
  be hidden inside sampled non-thermal electric demand.
- artifact contents must be sufficient for offline sampling without refitting
  or live services.

## Non-Thermal Electric Demand Model

**Fields**: `model_kind`, `local_step_baseline_kw`, `weather_response_terms`,
`training_day_count`, `residual_scale_summary`, `supported_weather_drivers`.

**Relationships**: Embedded inside one fitted demand artifact; consumed by the
sampler to produce non-thermal electric demand conditioned on weather traces.

**Validation rules**:

- the baseline and weather-response terms must align to the artifact timestep.
- returned sampled values must remain non-negative.
- the supported weather drivers must be explicit and must match the fields
  required from the weather trace.

## Cooling Demand Model

**Fields**: `model_kind`, `local_step_baseline_rt`, `weather_response_terms`,
`training_day_count`, `residual_scale_summary`, `supported_weather_drivers`,
`explicit_training_requirement`.

**Relationships**: Embedded inside one fitted demand artifact; consumed by the
sampler to produce cooling demand in `RT` conditioned on weather traces.

**Validation rules**:

- `explicit_training_requirement` must record that the fit used historical
  cooling-demand observations rather than decomposition from electric load.
- sampled cooling demand must remain non-negative.
- supported drivers must remain explicit and aligned to the weather contract.

## Shared Residual Model

**Fields**: `model_kind`, `intervals_per_day`, `output_order`,
`joint_residual_summary`, `correlation_matrix`, `sampling_notes`.

**Relationships**: Embedded inside one demand artifact; applied after the
output-specific conditional baselines to preserve cross-output correlation and
scenario-level variability.

**Validation rules**:

- `output_order` must be fixed to the first-release pair:
  `non_thermal_electric_demand_kw`, `cooling_demand_rt`.
- dimensions must align with the timestep and output count.
- residual sampling must not change the explicit separation between electric
  and cooling outputs.

## Demand Sampling Request

**Fields**: `artifact_id`, `weather_family_reference`, `num_steps`,
`scenario_count`, `paired_family_seed`, `scenario_index_order`.

**Relationships**: Submitted by a caller after loading a fitted demand
artifact and preparing a sampled weather family; produces one demand scenario
family.

**Validation rules**:

- `num_steps` must be positive and must match the referenced weather family.
- `scenario_count` must be positive and must match the referenced weather
  family.
- `paired_family_seed` defines the reproducibility surface for both the demand
  and weather family.
- `scenario_index_order` must preserve one-to-one alignment with the weather
  family.

## Sampled Demand Trace

**Fields**: `scenario_index`, `paired_family_seed`, `derived_identity`,
`weather_trace_reference`, `timestep_hours`,
`non_thermal_electric_demand_kw`, `cooling_demand_rt`,
`local_civil_step_labels`.

**Relationships**: Belongs to one demand scenario family; aligns to one
  sampled weather trace of the same scenario index; may feed one simulator
  paired-family evaluation.

**Validation rules**:

- both demand output series lengths must equal `num_steps`.
- the same paired-family seed and scenario ordering must reproduce the same
  trace.
- the sampled trace must remain aligned to the referenced weather trace
  timestep and scenario index.
- both output series must be explicit, even when one output is zero at every
  step.

## Demand Scenario Family

**Fields**: `family_id`, `artifact_reference`, `weather_family_reference`,
`paired_family_seed`, `scenario_count`, `num_steps`, `timestep_hours`,
`sampled_traces`.

**Relationships**: Produced by the demand sampling workflow; consumed by one
simulator paired-family evaluation request.

**Validation rules**:

- every sampled trace must share the same `num_steps` and `timestep_hours`.
- scenario indices must be unique within the family.
- family ordering must match the referenced weather family ordering exactly.

## Cooling Service Configuration

**Fields**: `service_path`, `local_electric_cooling`, `district_cooling_tariff`,
`source`, `notes`.

**Relationships**: Simulator-side configuration applied to one cooling-aware
scenario or scenario family; determines how sampled cooling demand is served
and settled.

**Validation rules**:

- `service_path` must be exactly one of `local-electric` or `district-cooling`
  in the first release.
- local-electric scenarios must define a reproducible `kW`-per-`RT`
  conversion factor.
- district-cooling scenarios must define a deterministic tariff for served
  `RT-hour`.
- mixed local-plus-district configuration is invalid.

## Local Electric Cooling Configuration

**Fields**: `source_name`, `electric_kw_per_rt`, `valid_for_feature_version`,
`notes`.

**Relationships**: Nested inside one cooling service configuration when the
service path is local electric cooling.

**Validation rules**:

- `electric_kw_per_rt` must be positive.
- the factor must be explicitly documented and reproducible for the first
  release.

## District Cooling Tariff

**Fields**: `currency`, `rate_per_rt_hour`, `time_alignment`, `tariff_name`.

**Relationships**: Nested inside one cooling service configuration when the
service path is district cooling; consumed by simulator settlement logic.

**Validation rules**:

- `rate_per_rt_hour` must be non-negative.
- `time_alignment` must match the scenario time grid semantics.
- tariff definition must be explicit whenever district settlement is requested.

## Cooling Service Result

**Fields**: `scenario_index`, `service_path`, `served_cooling_rt`,
`unserved_cooling_rt`, `local_cooling_electric_kw`,
`district_cooling_settlement`, `constraint_events`.

**Relationships**: Produced by simulator evaluation for one sampled demand
trace; paired with the corresponding electric and weather simulator outputs.

**Validation rules**:

- series lengths must align to the scenario time grid.
- locally served cooling contributes to site electric load only through
  `local_cooling_electric_kw`.
- served district cooling must not also appear in site electric load.
- `unserved_cooling_rt` must be explicit whenever full service is unavailable.

## Paired Simulator Family Evaluation Request

**Fields**: `base_scenario_reference`, `weather_family`, `demand_family`,
`cooling_service_configuration`, `summary_output_fields`, `numeric_tolerance`.

**Relationships**: Submitted to the simulator-side paired-family evaluator;
produces one cooling-aware weather-and-demand family result.

**Validation rules**:

- the base scenario must preserve existing deterministic simulator semantics
  aside from substituted weather and demand inputs.
- weather and demand families must share the same paired-family seed, scenario
  ordering, timestep, and horizon length.
- summary fields must be limited to documented comparison outputs.

## Paired Scenario Evaluation Result

**Fields**: `scenario_index`, `weather_reference`, `demand_reference`,
`non_thermal_electric_demand_kw`, `cooling_demand_rt`,
`local_cooling_electric_kw`, `served_cooling_rt`, `unserved_cooling_rt`,
`district_cooling_settlement`, `site_electric_load_kw`,
`net_grid_power_kw`, `unmet_load_kw`, `step_settlement`,
`total_settlement`, `blackout_active`, `constraint_events`.

**Relationships**: Belongs to one paired simulator family result; mirrors the
deterministic simulator trace surface while adding cooling-service accounting.

**Validation rules**:

- `site_electric_load_kw` must equal non-thermal electric demand plus local
  cooling electric demand for local-electric scenarios.
- district-cooled thermal service must not appear in `site_electric_load_kw`.
- blackout semantics remain grid-side only and do not modify fitted demand
  artifacts.
- result ordering must preserve the demand and weather family ordering.

## Demand Family Evaluation Result

**Fields**: `family_id`, `scenario_results`, `summary_statistics`,
`supported_summary_fields`, `paired_family_seed`, `timestep_hours`,
`cooling_service_path`.

**Relationships**: Produced from one paired simulator family evaluation
request; may feed later comparison or visualization layers.

**Validation rules**:

- `scenario_results` must preserve per-scenario ordering and scenario index.
- summaries must include stable statistics only for documented comparison
  outputs.
- repeated evaluation with the same paired-family seed, artifact pair, and
  scenario ordering must reproduce both scenario results and summary
  statistics.

## Lifecycle Notes

1. Prepare one aligned historical demand-plus-weather dataset from canonical
   weather and explicit demand series.
2. Fit one fixed-timestep demand artifact that preserves separate electric and
   cooling outputs.
3. Persist the artifact with supported schema version and provenance.
4. Load the artifact offline and sample one demand scenario family against a
   sampled weather family using one shared paired-family seed.
5. Evaluate the paired families against one cooling-aware simulator
   configuration and emit scenario results plus stable family summaries.
