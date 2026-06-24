# Data Model: TPM-Backed Planning And Simulator Dataset Export

This feature introduces a simulator-owned planning-dataset export surface, a
native `open_energy_lab.tpm` package for typed feature and SPN artifacts, and
an expanded `open_energy_lab.planning` package for optional model assembly and
solve workflows.

## Planning Export Request

**Fields**: `export_id`, `family_result_reference`, `weather_family_reference`,
`design_metadata_rows`, `flattened_series_fields`, `target_definition`,
`row_order_policy`, `include_provenance`, `numeric_tolerance`.

**Relationships**: Submitted by a caller after simulator family evaluation;
produces one persisted planning dataset artifact.

**Validation rules**:

- simulator result, weather family, and design metadata must align on
  scenario count and scenario ordering
- flattened fields must be limited to documented exportable series
- `target_definition` must identify exactly one planning target in the first
  release
- row-order policy must be deterministic and persisted in artifact metadata

## Planning Dataset Artifact

**Fields**: `dataset_id`, `schema_version`, `created_at`, `row_count`,
`horizon_steps`, `timestep_hours`, `column_order`, `rows`,
`design_feature_schema`, `series_field_schema`, `target_metadata`,
`provenance`, `export_configuration`.

**Relationships**: Produced by the simulator export workflow; consumed by TPM
fit and reload workflows; referenced by planning fixtures and review flows.

**Validation rules**:

- `schema_version` must be explicitly supported or load fails fast
- `column_order` must be deterministic and preserved exactly across reloads
- each row must contain one value for every column in the schema
- artifact metadata must preserve enough provenance to trace the dataset back
  to simulator family identifiers, seeds, and source fixtures

## Planning Dataset Row

**Fields**: `scenario_index`, design columns such as `battery_*` and
`solar_*`, flattened horizon-indexed columns such as `ghi_0`, `load_0`,
`unmet_load_0`, optional summary columns, `shortfall`, and `row_provenance`.

**Relationships**: Belongs to one planning dataset artifact; supplies one
training observation for the TPM workflow.

**Validation rules**:

- one row corresponds to exactly one simulation instance
- flattened horizon columns must use the stable `<field>_<step>` naming rule
- `shortfall` must be derivable from the row’s exported simulator outcome
  fields and the artifact timestep
- missing design metadata for a row is invalid in the first release

## Shortfall Target Definition

**Fields**: `target_name`, `numerator_source_field`,
`denominator_source_field`, `aggregation_rule`, `threshold_default`,
`supported_query_mode`, `notes`.

**Relationships**: Embedded in the planning dataset artifact and TPM artifact;
consumed by TPM queries and planning-problem definitions.

**Validation rules**:

- `target_name` is `shortfall` in the first release
- `aggregation_rule` must document energy-based horizon aggregation
- threshold semantics must remain distinct from chance-limit `epsilon`
- the definition must remain library-owned rather than notebook-owned

## Typed Feature Schema

**Fields**: `feature_name`, `feature_role`, `feature_type`,
`modifiable`, `monotonicity`, `bounds`, `discrete_values`,
`ordering`, `normalization_rule`, `legacy_reference`.

**Relationships**: Stored inside the TPM artifact; used by fit, reload,
query, and planning-encoding workflows.

**Validation rules**:

- supported first-release feature types are continuous, binary,
  categorical, and mixed
- bounds and categorical value domains must be explicit where required for
  encoding or validation
- feature ordering must be stable and persisted
- target and decision features must remain distinguishable in metadata

## TPM Artifact

**Fields**: `artifact_id`, `schema_version`, `created_at`,
`dataset_reference`, `feature_schema`, `target_definition`,
`fit_configuration`, `spn_payload`, `spn_payload_format`,
`query_configuration`, `approximation_metadata`, `provenance`.

**Relationships**: Produced from one planning dataset artifact; consumed by
query and planning workflows.

**Validation rules**:

- artifact loading must fail fast for unsupported schema versions
- the artifact must preserve all feature typing needed for offline query
- the artifact schema version must document whether `spn_payload` is embedded
  directly or interpreted as a locator to an external persisted payload
- approximation metadata must document the canonical piecewise planning path
- provenance must include enough information to reproduce fit inputs and seed
  expectations

## TPM Query Request

**Fields**: `artifact_reference`, `decision_assignments`,
`marginalized_features`, `target_event`, `output_mode`,
`numeric_tolerance`.

**Relationships**: Submitted by callers to obtain conditional probability or
log-likelihood outputs from a loaded TPM artifact.

**Validation rules**:

- decision assignments must respect the artifact feature schema
- omitted non-decision variables are marginalized explicitly
- `target_event` must refer to the single configured target definition
- output mode must be documented as conditional probability or log-likelihood

## Piecewise Approximation Contract

**Fields**: `approximation_kind`, `leaf_encoding_mode`, `sum_encoding_mode`,
`breakpoint_policy`, `mio_epsilon`, `tolerance`, `legacy_reference_paths`.

**Relationships**: Stored in TPM artifact metadata when planning-compatible
encodings are prepared; consumed by planning model assembly.

**Validation rules**:

- `approximation_kind` is piecewise in the canonical first release
- breakpoint policy must be explicit and reproducible
- lower-tangent-only formulations must not be labeled canonical
- any tolerance used for fixture validation must be documented

## Planning Problem Definition

**Fields**: `problem_id`, `tpm_artifact_reference`, `decision_features`,
`cost_terms`, `shortfall_threshold`, `chance_limit_epsilon`,
`objective_direction`, `solver_configuration`, `approximation_contract`,
`notes`.

**Relationships**: Submitted to `open_energy_lab.planning`; produces either an
assembled model, a solved design, or deterministic infeasibility diagnostics.

**Validation rules**:

- supported first-release decision variables are battery and solar only
- `shortfall_threshold` and `chance_limit_epsilon` must both be explicit or
  defaulted through documented fixture values
- cost terms must be deterministic for the first release
- solver configuration must remain optional and documented

## Planning Solution Summary

**Fields**: `problem_id`, `status`, `selected_design`, `objective_value`,
`estimated_shortfall_risk`, `threshold`, `chance_limit_epsilon`,
`feasibility_diagnostics`, `solver_metadata`.

**Relationships**: Produced by the optional planning solve workflow; used by
review fixtures and user-facing diagnostics.

**Validation rules**:

- successful solutions must return one design assignment and objective value
- infeasible cases must return deterministic diagnostics
- reported risk must align with the configured target event
- solver metadata must record enough information to explain reproducibility
  expectations
