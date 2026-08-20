# Data Model: TPM-Backed Planning And Simulator Dataset Export

This feature introduces a simulator-owned planning-dataset export surface, a
native `open_energy_lab.tpm` package for typed feature and SPN artifacts, and
an expanded `open_energy_lab.planning` package for model assembly and required
default HiGHS solve workflows.

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
`solar_*`, `controller_name`, flattened horizon-indexed columns such as
`ghi_0`, `pv_generation_0`, `load_0`, `controller_request_0`,
`battery_power_0`, `battery_soc_0`, `grid_available_0`, and `unmet_load_0`,
optional summary columns, `shortfall`, and `row_provenance`.

**Relationships**: Belongs to one planning dataset artifact; supplies one
training observation for the TPM workflow.

**Validation rules**:

- one row corresponds to exactly one simulation instance
- flattened horizon columns must use the stable `<field>_<step>` naming rule
- `shortfall` must be derivable from the row’s exported simulator outcome
  fields and the artifact timestep
- each `unmet_load_<step>` value must be no greater than the corresponding
  `load_<step>` value; curtailed battery charging is not site-load shortfall
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
`fit_configuration`, `backend_generation`, `backend_api_version`,
`execution_mode`, `spn_payload`, `spn_payload_format`, `payload_hash`,
`query_configuration`, `approximation_metadata`, `provenance`.

**Relationships**: Produced from one planning dataset artifact; consumed by
query and planning workflows.

**Validation rules**:

- artifact loading must fail fast for unsupported schema versions
- current-SPFlow production artifacts use schema version `2`; schema version
  `1` is accepted only far enough to return an explicit incompatibility/refit
  error
- the artifact must preserve all feature typing needed for offline query
- schema-v2 `spn_payload` is a project-relative locator to a separately
  persisted model sidecar; its SHA-256 digest is verified before loading, and
  manifest/sidecar replacement uses atomic sibling-file writes
- production artifacts must identify the current SPFlow backend generation,
  API version, model-sidecar format, and integrity hash
- pre-1.0 SPFlow models are incompatible migration inputs and must be refitted;
  they cannot be loaded as current production payloads
- `execution_mode` must be `production` for normal fit/query behavior;
  `fixture_replay` is allowed only for explicitly invoked test evidence
- approximation metadata must document the canonical piecewise planning path
- provenance must include enough information to reproduce fit inputs and seed
  expectations

## TPM Query Request

**Fields**: `artifact_reference`, `decision_assignments`,
`marginalized_features`, `target_event`, `output_mode`,
`numeric_tolerance`, `execution_mode`.

**Relationships**: Submitted by callers to obtain conditional probability or
log-likelihood outputs from a loaded TPM artifact.

**Validation rules**:

- decision assignments must respect the artifact feature schema
- omitted non-decision variables are marginalized explicitly
- `target_event` must refer to the single configured target definition
- output mode must be documented as conditional probability or log-likelihood
- production mode requires a valid current-SPFlow payload and fails explicitly
  if it is absent, incompatible, or fails integrity validation
- empirical evaluation is legal only when `execution_mode` is explicitly
  `fixture_replay`; it never activates automatically

## Piecewise Approximation Contract

**Fields**: `approximation_kind`, `leaf_encoding_mode`, `sum_encoding_mode`,
`breakpoint_policy`, `mio_epsilon`, `tolerance`, `backend_compiler_version`,
`supported_spflow_module_types`, `legacy_reference_paths`.

**Relationships**: Stored in TPM artifact metadata when planning-compatible
encodings are prepared; consumed by planning model assembly.

**Validation rules**:

- `approximation_kind` is piecewise in the canonical first release
- breakpoint policy must be explicit and reproducible; the canonical fixture
  configuration uses five breakpoints, and any explicit override is persisted
- lower-tangent-only formulations must not be labeled canonical
- any tolerance used for fixture validation must be documented
- a current-SPFlow compiler must declare the exact tensorized module/leaf
  subset it supports and fail on unsupported graph structures
- the first-release subset is sum/product structure with one output channel
  and repetition, Normal continuous leaves, Bernoulli binary leaves, and
  Categorical categorical leaves on separate typed scopes
- arbitrary Torch modules, custom leaves, multiple channels/repetitions,
  uncompileable shared subgraphs, and unconverted legacy histogram leaves are
  rejected with their module type and scope
- compiled conditional probabilities must be parity-checked against current
  SPFlow `model.log_likelihood(...)` results within `1e-6` maximum absolute
  error; repeated canonical evaluations must agree within `1e-9`

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
- omission of solver configuration selects the required default
  `solver_name="highs"`; explicitly selected supplemental solvers remain
  documented
- the default HiGHS configuration uses seed `13`, one thread, a 30-second
  fixture time limit, and `1e-9` repeatability tolerance

## Planning Solution Summary

**Fields**: `problem_id`, `status`, `selected_design`, `objective_value`,
`estimated_shortfall_risk`, `threshold`, `chance_limit_epsilon`,
`feasibility_diagnostics`, `solver_metadata`.

**Relationships**: Produced by the planning solve workflow; used by
review fixtures and user-facing diagnostics.

**Validation rules**:

- successful solutions must return one design assignment and objective value
- infeasible cases must return deterministic diagnostics
- reported risk must align with the configured target event
- solver metadata must record enough information to explain reproducibility
  expectations
- routine results record Pyomo, `highspy`, solver-interface, termination,
  options, and version metadata; Gurobi results are supplemental

## Canonical TMY Cache Request

**Fields**: `latitude`, `longitude`, `timezone_name`, `endpoint_url`,
`use_horizon`, optional `start_year`, optional `end_year`, `timeout_seconds`,
`cache_path`, `cache_status`, `payload_sha256`.

**Validation rules**:

- the default endpoint is explicitly versioned PVGIS 5.3
- source years are supplied as a pair
- a compatible cache is keyed by the complete location and API request
- missing cache plus disabled or failed network fetch is an explicit failure
- the canonical hourly dataset is fitted directly without a second fetch

## Held-Out Study Assessment

**Fields**: candidate name, validation Brier score, compilability, SPN node
count, per-configuration native probability, empirical final-test probability,
confidence interval, mean error, maximum error, label coverage, selected-design
one-sided upper risk bound, native/MIO discrepancy, blocking reasons.

**Validation rules**:

- only compilable candidates may be selected
- validation Brier score is primary and smaller node count breaks ties
- final-test evidence is independent of training and validation manifests
- calibration requires mean error at most 0.05, maximum error at most 0.10,
  both labels, and selected native probability inside its confidence interval
- recommendation additionally requires native/MIO discrepancy at most `1e-6`
  and a one-sided held-out 95% risk bound no greater than epsilon
