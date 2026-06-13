# Feature Specification: Stochastic Weather Generation And Simulator Integration

**Feature Branch**: `007-stochastic-weather`  
**Created**: 2026-06-13  
**Status**: Draft  
**Input**: User description: "Specify the next Open Energy Lab feature as a stochastic weather generation and simulator integration capability."

## Purpose *(mandatory)*

Add a unified-library weather capability that starts from geolocation, fetches
TMY weather data through a library-owned workflow, fits a stochastic weather
model, persists the fitted artifact, and later reloads that artifact to sample
many weather traces for simulator use without requiring network access.

This feature moves Open Energy Lab beyond the current deterministic
PV-supporting weather surface into a reusable stochastic workflow while
preserving the existing deterministic weather path for debugging, fixture-based
validation, and reproducible regression checks. The simulator remains the owner
of execution semantics; the new weather capability supplies sampled inputs and
explicit outage disturbances rather than absorbing simulator responsibilities.

## Clarifications

### Session 2026-06-13

- Q: What is the source of blackout disturbances in the first release? → A: Caller-configured simulator disturbances stored in scenario configuration, separate from the fitted weather artifact.
- Q: How should persisted weather artifacts behave across schema-version mismatches? → A: Load only explicitly supported schema versions and fail fast on unsupported mismatches.
- Q: What outage semantics should blackout intervals use in the first release? → A: Grid outage only; no grid import or export, PV and battery may still serve load, and remaining shortfall is tracked as unmet load.
- Q: How should timestep resolution behave for persisted fitted weather artifacts? → A: Each fitted artifact is tied to one timestep resolution; sampling must use that same resolution, and different resolutions require separate artifacts.
- Q: What should happen if the fetched TMY source cannot provide every required canonical weather variable? → A: The fit workflow fails fast and does not create a partial artifact.
- Q: What should the stable first-release scenario-family result return? → A: Per-scenario traces plus built-in basic family summaries such as min/mean/max and selected percentiles.
- Q: What should the stable first-release reproducibility seed surface be? → A: Callers provide one family seed, and the library deterministically derives each scenario instance from that seed plus scenario index.
- Q: Which percentile set should the stable first-release family summaries include? → A: Fixed percentiles 5th, 50th, and 95th.
- Q: What time basis should the stable first-release weather model use for fitting and sampling? → A: Fit and sample in location-local civil time, while materialized sampled traces still provide canonical `timestamp_utc` values.
- Q: Which outputs should the stable first-release family summaries cover? → A: Documented core simulator outputs only, such as PV generation, net-grid power, unmet load, and settlement metrics.

## Scope Classification *(mandatory)*

- **Feature type**: Migration plus new library capability
- **Target surface**: Public library weather API, persisted model artifact,
  and simulator integration contract for stochastic scenario families
- **Legacy reference paths**:
  - `legacy/old_tpm/src_py/weather/fetch.py`
  - `legacy/old_tpm/src_py/weather/pipeline.py`
  - `legacy/old_tpm/src_py/weather/models/gaussian.py`
  - `legacy/old_tpm/src_py/weather/models/enhanced.py`
  - `legacy/old_tpm/src_py/weather/analysis/drops.py`
  - `legacy/old_tpm/src_py/simulator/common/weather.py`
  - `legacy/old_tpm/src_py/simulator/common/pv.py`
- **New-code location**:
  - `src/open_energy_lab/weather`
  - `src/open_energy_lab/simulator`
  - matching validation under `tests/unit`, `tests/integration`, and
    `tests/fixtures` as needed

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fit And Persist A Location-Specific Weather Model (Priority: P1)

As a library user, I need to provide a geolocation and produce a persisted
stochastic weather artifact so that later workflows can sample realistic
weather without repeating network fetches or refits.

**Why this priority**: The end-to-end workflow begins with a location-driven
training path. Without a persisted artifact, the capability is not reusable,
offline-safe, or reproducible.

**Independent Test**: A reviewer can fit a weather model from a deterministic
TMY fixture or recorded fetch response, inspect the resulting artifact, and
reload it later in an offline environment to confirm it still supports
sampling.

**Acceptance Scenarios**:

1. **Given** a latitude and longitude plus a reachable TMY data source,
   **When** the library fit workflow is executed, **Then** it fetches the TMY
   data, normalizes every supported weather variable into the library's
   canonical schema, fits the stochastic model, and writes a versioned fitted
   artifact with provenance and schema metadata.
2. **Given** a previously persisted fitted artifact and no network access,
   **When** the artifact is loaded later, **Then** the library can sample new
   stochastic weather traces without refetching source data or recomputing fit
   parameters.

---

### User Story 2 - Sample Many Arbitrary-Horizon Weather Instances (Priority: P2)

As a researcher, I need to generate many distinct stochastic weather traces for
any requested horizon length so that I can explore scenario families rather
than only one fixed deterministic weather path or whole-day outputs.

**Why this priority**: The main value of the feature is to support stochastic
scenario exploration. Arbitrary horizon support is required for simulator runs
that do not align exactly to one day.

**Independent Test**: A reviewer can load a persisted fitted artifact, request
multiple stochastic samples for several positive `num_steps` values, and verify
that every sample contains the full canonical variable set, the requested
horizon length, and distinct seeded instances.

**Acceptance Scenarios**:

1. **Given** a fitted weather artifact, a requested number of scenarios, and a
   positive `num_steps`, **When** the sampling workflow is called, **Then** it
   returns the requested number of distinct stochastic weather instances and
   each instance contains exactly `num_steps` aligned values for every
   supported weather variable.
2. **Given** a requested horizon that is not an exact whole-day multiple,
   **When** sampling is performed, **Then** the library still returns complete
   aligned traces without truncation to a fixed day shape and without requiring
   the caller to manually stitch daily outputs together.

---

### User Story 3 - Evaluate Stochastic Weather In The Simulator While Preserving Deterministic Debugging (Priority: P3)

As a simulator maintainer, I need stochastic weather samples to integrate with
the existing simulator while keeping the current deterministic weather path
available so that I can explore weather-driven scenario families without losing
debuggability or deterministic regression evidence.

**Why this priority**: Simulator adoption is the point of the feature, but the
existing deterministic path remains the reference surface for debugging and
validation.

**Independent Test**: A reviewer can execute one deterministic
`BatteryLoadPVScenario` using the current fixed-weather path and also execute a
family of weather-sampled runs using the same base scenario configuration,
confirming that deterministic single-run behavior remains available and that
stochastic family outputs expose sampled weather and outage semantics clearly.

**Acceptance Scenarios**:

1. **Given** an existing deterministic simulator scenario,
   **When** deterministic weather inputs are supplied directly,
   **Then** the simulator continues to execute through the current deterministic
   path without requiring a stochastic fit artifact.
2. **Given** a base simulator configuration plus a loaded fitted weather
   artifact, **When** a stochastic scenario family is evaluated, **Then** the
   simulator receives sampled weather traces and any associated blackout
   disturbances for each scenario instance while returning scenario-indexed
   results that can be compared across the family.

### Edge Cases

- The requested location is syntactically valid but the TMY source cannot serve
  data for that point.
- The fetched TMY response omits one or more expected fields or uses source
  labels that do not map cleanly into the canonical schema; the fit workflow
  must fail fast and refuse to create a partial artifact in the first release.
- Sampling is requested for horizons shorter than one day, longer than one day,
  or not divisible by the fitted base interval.
- Sampling is requested at a timestep resolution different from the fitted
  artifact's stored resolution; the library must reject the request rather than
  silently resampling in the first release.
- The same artifact is sampled repeatedly with the same seed and configuration;
  outputs must be reproducible, but different scenario indices must still be
  distinguishable when requested.
- Sampled values violate physical bounds such as negative irradiance, negative
  wind speed, humidity outside `[0, 100]`, or non-positive air pressure.
- A cloud event and a blackout event overlap in time; the library must treat
  them as distinct phenomena rather than collapsing both into irradiance dips.
- During blackout intervals, local PV and battery may still operate while grid
  import and export are disabled; any remaining demand shortfall must be
  represented explicitly as unmet load rather than hidden in ordinary
  settlement traces.
- A persisted artifact is loaded after a schema revision; compatibility or
  failure behavior must be explicit, deterministic, and fail fast when the
  artifact schema version is unsupported.
- Users need deterministic fixtures for schema and integration validation even
  when stochastic statistical checks cannot prove perfect realism.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST accept geolocation input and provide a
  library-owned workflow that fetches TMY weather data for that location.
- **FR-002**: The feature MUST normalize fetched TMY data into one canonical
  weather schema owned by Open Energy Lab rather than exposing provider-specific
  raw labels as the primary runtime contract.
- **FR-003**: The canonical weather schema for the first release MUST include
  every weather variable already recognized by the current simulator weather
  schema:
  `timestamp_utc`,
  `dry_bulb_air_temperature_c`,
  `global_horizontal_irradiance_w_per_m2`,
  `direct_beam_irradiance_w_per_m2`,
  `diffuse_horizontal_irradiance_w_per_m2`,
  `relative_humidity_pct`,
  `infrared_radiation_downwards_w_per_m2`,
  `windspeed_10m_m_per_s`,
  `wind_direction_10m_deg`,
  and `surface_air_pressure_pa`.
- **FR-004**: The feature MUST define the canonical source-label mapping and
  metadata provenance for each supported weather variable so that later schema
  evolution remains explicit and reviewable.
- **FR-004a**: In the first release, fetched TMY data MUST be normalized to the
  location's local civil time for fitting and sampling semantics, while
  materialized sampled traces MUST still provide canonical `timestamp_utc`
  values in the public weather schema.
- **FR-005**: The feature MUST promote the full ten-field canonical weather
  schema to supported status for normalization, fitted artifacts, and sampled
  weather traces. The preserved deterministic simulator weather path remains a
  debugging and regression surface and is not required to expose every
  canonical field unless a simulator integration in this feature explicitly
  consumes that field.
- **FR-006**: The feature MUST fit stochastic model parameters from fetched TMY
  data for every supported weather variable in the canonical schema.
- **FR-006a**: In the first release, the fit workflow MUST require every
  required canonical weather variable to be present and mappable from the
  fetched TMY source. If any required variable is unavailable, the workflow
  MUST fail fast and MUST NOT create a partial fitted artifact.
- **FR-007**: The first stable release MUST preserve temporal structure within
  each variable and realistic relationships across variables and across time in
  sampled traces.
- **FR-008**: The feature MUST explicitly reject an independently sampled
  per-variable model as the only stable public behavior unless it also
  demonstrably preserves the documented cross-variable and temporal validation
  criteria for the supported weather set.
- **FR-009**: The feature MUST treat preservation of cross-variable
  relationships as more important than preserving the exact legacy
  separate-per-variable training structure. A joint multivariate weather model,
  or an internal design with equivalent joint-behavior guarantees, is the
  preferred stable direction for this feature.
- **FR-010**: The feature MUST persist fitted stochastic weather artifacts in a
  versioned, loadable format that contains enough information to sample later
  without network access or refitting.
- **FR-010a**: Artifact loading in the first release MUST accept only
  explicitly supported schema versions and MUST fail fast on unsupported
  version mismatches rather than attempting silent best-effort loading or
  automatic migration.
- **FR-011**: The persisted fitted artifact MUST record provenance including
  location, source, canonical variable set, fit configuration, random-seed
  inputs when relevant, schema version, and any event-model calibration data
  needed for later sampling.
- **FR-011a**: The persisted fitted artifact MUST record its timestep
  resolution explicitly as part of the stable artifact contract.
- **FR-012**: The feature MUST provide a sampling workflow that accepts at
  least a requested horizon length, a requested number of stochastic instances,
  and reproducibility inputs such as a seed or equivalent deterministic control
  surface.
- **FR-012a**: In the first release, sampling from a fitted artifact MUST use
  the same timestep resolution stored in that artifact. Requests that imply a
  different timestep resolution MUST fail fast rather than silently aggregating,
  interpolating, or resampling.
- **FR-012b**: In the stable first-release sampling surface, callers MUST be
  able to provide one family-level seed, and the library MUST deterministically
  derive each scenario instance from that family seed plus scenario index.
- **FR-013**: The feature MUST support arbitrary positive horizon lengths by
  generating as many steps as needed for `num_steps`, not only whole-day output
  blocks.
- **FR-014**: The feature MUST let users generate many distinct stochastic
  weather instances for the same horizon request without mutating the persisted
  fitted artifact.
- **FR-015**: The feature MUST preserve the current deterministic weather path
  for debugging and reproducible validation. `BatteryLoadPVScenario` remains
  the deterministic single-run simulator surface for direct fixed-weather
  evaluation, and deterministic simulator workflows MUST NOT require a fitted
  stochastic artifact or stochastic-family types when they do not need them.
- **FR-016**: The feature MUST define a simulator-facing integration contract
  that lets one base simulator setup be evaluated against a family of sampled
  weather instances while keeping simulator execution semantics owned by
  `open_energy_lab.simulator`.
- **FR-017**: The feature MUST define how stochastic weather interacts with the
  current `BatteryLoadPVScenario` behavior, including whether weather-sampled
  scenario families introduce new scenario-family inputs, new family-result
  surfaces, or both.
- **FR-017b**: Stochastic simulator integration adds a scenario-family surface
  that binds one base deterministic simulator configuration to many sampled
  weather instances and returns scenario-indexed results without changing the
  meaning of the deterministic single-run path.
- **FR-017c**: The stable first-release scenario-family result MUST include
  both per-scenario traces and built-in basic family summaries for supported
  output fields, including at least min, mean, max, and the fixed 5th, 50th,
  and 95th percentiles.
- **FR-017d**: In the first release, built-in family summaries MUST cover only
  documented core simulator outputs, including PV generation, net-grid power,
  unmet load, and settlement metrics. Raw weather variables are not part of
  the stable family-summary surface.
- **FR-019**: The feature MUST represent ordinary cloud or irradiance
  attenuation events as weather-side stochastic behavior that can span multiple
  contiguous timesteps.
- **FR-020**: The feature MUST represent blackout behavior separately from
  irradiance attenuation. Blackouts are simulator-side power-availability
  disturbances with explicit outage semantics rather than merely low-sunlight
  weather samples.
- **FR-021**: The simulator integration contract MUST define how blackout
  disturbances affect energy-flow evaluation, result traces, and scenario
  interpretation for weather-driven runs.
- **FR-021a**: During blackout intervals, the simulator contract MUST make
  outage semantics explicit rather than silently treating the interval as an
  ordinary low-irradiance timestep. The resulting traces MUST reveal that the
  run experienced a power-availability disturbance.
- **FR-021b**: In the first release, blackout intervals mean grid outage only:
  grid import and export are unavailable, local PV and battery may continue
  serving load, and any remaining shortfall MUST be represented explicitly as
  unmet load in the scenario results.
- **FR-022**: In the first release, blackout disturbances MUST be
  caller-configured simulator-side inputs stored in scenario configuration, and
  they MUST remain separate from the fitted weather artifact rather than being
  fitted from TMY weather data.
- **FR-023**: The feature MUST keep blackout semantics distinct from PV
  generation semantics so that a run can contain normal low-irradiance periods,
  cloud-driven irradiance drops, blackout outages, or overlapping combinations
  of those phenomena.
- **FR-024**: The feature MUST define stable conceptual entities for at least
  canonical fetched weather data, fitted weather artifact, sampled weather
  trace, blackout disturbance trace, and simulator scenario-family results.
- **FR-025**: The feature MUST define artifact and sampling schemas that are
  deterministic to validate with committed fixtures even though sampled outputs
  are stochastic.
- **FR-026**: The feature MUST define stochastic validation criteria for
  distribution shape, physical bounds, temporal continuity, event-duration
  behavior, and cross-variable relationship preservation.
- **FR-027**: The feature MUST define deterministic validation evidence for
  artifact loading, schema compatibility, offline sampling, and simulator
  integration contracts.
- **FR-027a**: Deterministic validation MUST include at least one negative case
  proving that an unsupported artifact schema version is rejected with an
  explicit load failure.
- **FR-028**: The feature MUST state which public surfaces are stable in the
  first release and which, if any, remain experimental.
- **FR-028a**: The stable first-release surface is:
  geolocation-driven fit,
  canonical weather normalization,
  versioned fitted-artifact persistence,
  offline artifact loading,
  arbitrary-horizon seeded sampling,
  blackout-disturbance representation,
  simulator scenario-family consumption with built-in basic family summaries,
  and the preserved deterministic path.
- **FR-028b**: Experimental first-release surfaces, if exposed at all, are:
  alternative stochastic model backends,
  advanced calibration knobs beyond the default workflow,
  raw-provider extra fields beyond the canonical schema,
  and diagnostic-only statistical outputs that are not required for sampling or
  simulator execution.
- **FR-030**: If alternative model classes, tuning knobs, or diagnostic
  backends are exposed, they MUST be clearly marked experimental unless this
  spec explicitly promotes them to the stable surface.
- **FR-031**: The feature MUST classify any fetch dependency, network-backed
  service dependency, and scientific fitting dependency as core or optional,
  and sampling from an already fitted artifact MUST remain available without
  network access.
- **FR-032**: The feature MUST keep notebooks, dashboards, W&B workflows,
  SLURM or GPU workflows, and legacy runtime imports out of the core capability.
- **FR-033**: The feature MUST require implementation work to cite exact legacy
  source paths for behaviors preserved, improved, or rejected.
- **FR-034**: The feature MUST explicitly preserve, improve, or reject the
  following legacy behaviors:
  geolocation-driven TMY fetch,
  source-data time normalization,
  daily-profile weather synthesis,
  irradiance-drop augmentation,
  and simulator weather-to-PV integration.
- **FR-035**: The feature MUST explicitly reject legacy runtime coupling,
  city-code-only entry points, hard-coded fixed-day sampling assumptions, and
  any treatment of blackout semantics as mere irradiance reduction.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**:
  - `legacy/old_tpm/src_py/weather/fetch.py`
  - `legacy/old_tpm/src_py/weather/pipeline.py`
  - `legacy/old_tpm/src_py/weather/models/gaussian.py`
  - `legacy/old_tpm/src_py/weather/models/enhanced.py`
  - `legacy/old_tpm/src_py/weather/analysis/drops.py`
  - `legacy/old_tpm/src_py/simulator/common/weather.py`
  - `legacy/old_tpm/src_py/simulator/common/pv.py`
- **Behavior to preserve**:
  - location-driven TMY fetch as the upstream source concept
  - time-normalized weather preprocessing before model fitting
  - stochastic weather trace synthesis from fitted parameters
  - explicit modeling of irradiance-drop events beyond a perfectly smooth solar
    profile
  - simulator use of weather traces to derive PV behavior
- **Behavior to improve or drop**:
  - improve the current factorized legacy approach so the stable contract
    preserves cross-variable relationships rather than sampling each variable in
    isolation
  - improve the current fixed-day shape so arbitrary `num_steps` horizons are
    supported
  - improve artifact ownership so fitted parameters are persisted and reloadable
    inside the unified library
  - improve input generality so callers provide geolocation rather than a small
    hard-coded city list
  - drop any legacy runtime imports or reference-only coupling
  - drop any interpretation of blackout events as equivalent to irradiance dips
- **Parity evidence**:
  - deterministic fetch-normalization fixtures showing canonical variable
    mapping
  - committed fitted-artifact fixtures with schema and provenance checks
  - seeded sampling validation cases covering arbitrary horizons
  - simulator integration fixtures demonstrating both deterministic and
    stochastic family evaluation contracts
  - documented stochastic acceptance checks for temporal, event, and
    cross-variable behavior

### Key Entities *(include if feature involves data or API design)*

- **Canonical Weather Dataset**: One location-specific, time-aligned TMY-backed
  dataset in the library's canonical variable schema plus source metadata,
  provenance, canonical `timestamp_utc` values, and local-civil-time alignment
  metadata used for fitting and sampling.
- **Fitted Weather Model Artifact**: A persisted, versioned artifact containing
  fitted stochastic parameters, variable metadata, provenance, schema version,
  fixed timestep resolution, local-civil-time fitting basis metadata, and any
  event-calibration data needed for offline sampling.
- **Sampled Weather Trace**: One stochastic instance containing aligned values
  for every supported weather variable for a requested horizon length, plus
  sample metadata such as family seed, derived scenario identity, scenario
  index, and event annotations.
- **Cloud Event Annotation**: Metadata describing contiguous multi-step
  irradiance attenuation behavior that belongs to the sampled weather trace.
- **Blackout Disturbance Trace**: A simulator-consumable description of outage
  periods and outage semantics that is separate from raw weather values and is
  visible in scenario outputs as a true availability disturbance. In the first
  release it is supplied through scenario configuration, not learned from the
  fitted weather artifact.
- **Weather Scenario Family**: A collection of sampled weather instances and
  optional blackout disturbances evaluated against one base simulator setup.
- **Weather Scenario Family Result**: Scenario-indexed simulator outputs that
  preserve per-instance weather context, expose blackout intervals and any
  unmet-load trace they create, allow cross-scenario comparison, include
  built-in basic family summaries such as min, mean, max, and fixed 5th, 50th,
  and 95th percentiles for documented core simulator outputs only, and remain
  reproducible from the same family seed plus scenario ordering.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Existing unified-library Python runtime, current
  simulator deterministic surfaces, and lightweight serialization support for
  persisted artifacts
- **Optional dependencies**: Any network-backed TMY fetch client or heavier
  scientific fitting stack needed for artifact creation, provided they are
  isolated from deterministic simulator imports and offline artifact sampling
- **External services**: One TMY data provider during fetch-and-fit workflows;
  none required for loading persisted artifacts or sampling offline
- **Hardware assumptions**: CPU-only local workstation operation for fitting,
  sampling, and simulator validation

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full workflow from geolocation input to a
  persisted fitted artifact and later reload that artifact to sample weather
  offline without touching `legacy/*` runtime code.
- **SC-001a**: Validation includes a deterministic negative case proving that a
  fetch response missing any required canonical weather variable is rejected
  without producing a persisted artifact.
- **SC-002**: For any positive horizon length exercised by the validation
  suite, the sampler returns exactly the requested number of scenario instances
  and exactly `num_steps` aligned values for every supported weather variable.
- **SC-003**: Repeated family sampling from the same persisted artifact with
  the same family seed, scenario count, and scenario ordering produces
  identical per-scenario outputs and family summaries, while different family
  seeds or scenario indices produce distinct sampled instances.
- **SC-004**: Deterministic battery-load-PV regression fixtures continue to
  execute through the current fixed-weather path without requiring a stochastic
  fit artifact.
- **SC-004a**: For blackout validation fixtures, simulator results explicitly
  show disabled grid exchange during outage intervals and track any unmet load
  caused by insufficient local supply.
- **SC-005**: Validation draws from a fixed fitted artifact satisfy these
  stochastic checks against the fitted TMY baseline:
  - irradiance fields and wind speed are never negative
  - relative humidity stays within `[0, 100]`
  - surface air pressure stays strictly positive
  - repeated sampling preserves lag-1 autocorrelation for
    `dry_bulb_air_temperature_c`,
    `global_horizontal_irradiance_w_per_m2`, and `relative_humidity_pct`
    within an absolute tolerance of `0.15`
  - repeated sampling preserves pairwise correlation for the irradiance trio
    and the temperature-humidity pair within an absolute tolerance of `0.20`
  - sampled cloud events are contiguous for at least `95%` of annotated events
    and have a mean duration within `1` timestep of the fitted event model
  - stochastic acceptance is evaluated from `100` sampled scenarios generated
    with one fixed artifact, `num_steps=168`, and family seeds `0` through `9`
  - lag-1 autocorrelation and pairwise-correlation checks are computed on the
    per-scenario series and compared against the fitted TMY baseline using the
    mean absolute error across the sampled family
  - cloud-event contiguity is evaluated only on annotated irradiance events
    whose base irradiance exceeds the artifact's minimum event threshold
- **SC-006**: Persisted fitted-artifact fixtures can be loaded in an offline
  test environment and pass provenance and simulator-contract checks
  deterministically, while unsupported schema versions fail fast in a
  deterministic validation case.
- **SC-006a**: Sampling validation shows that an artifact can be used only at
  its stored timestep resolution in the first release, and mismatched
  resolution requests fail fast deterministically.
- **SC-006b**: Scenario-family validation shows that the stable family result
  returns both per-scenario traces and deterministic basic family summaries for
  documented core simulator outputs only, including min, mean, max, and fixed
  5th, 50th, and 95th percentiles.

## Assumptions

- The first release targets Python library users working through
  `src/open_energy_lab` surfaces rather than notebooks, dashboards, or service
  UIs.
- The existing deterministic simulator weather path remains the debugging and
  regression reference even after stochastic weather support is added.
- The supported canonical variable set for the first release is the full set of
  weather fields already recognized by the current simulator weather schema; raw
  provider-specific extras remain non-core until a later spec promotes them.
- The first release does not support partial fitted weather artifacts; a source
  either provides the full required canonical variable set or the fit workflow
  fails.
- `num_steps` is counted in the fitted artifact's stored timestep resolution;
  callers who need another timestep resolution create or load a different
  fitted artifact.
- The stable first-release model basis is location-local civil time even though
  public sampled traces continue to expose canonical `timestamp_utc` values.
- Preserving realistic cross-variable and temporal behavior is a stable outcome
  requirement, but the exact internal statistical method may evolve as long as
  the public artifact and simulator contracts remain satisfied.
- Blackout events may require a distinct calibration or configuration source
  from ordinary irradiance modeling, but they are still part of the first
  release contract for simulator-side stochastic weather runs.
- If external fetch services are unavailable, deterministic fixtures and
  persisted artifacts remain the required validation evidence for core library
  behavior.
