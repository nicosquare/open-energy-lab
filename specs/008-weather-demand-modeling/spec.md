# Feature Specification: Weather-Conditioned Demand Modeling

**Feature Branch**: `008-weather-demand-modeling`  
**Created**: 2026-06-15  
**Status**: Draft  
**Input**: User description: "Specify the next Open Energy Lab feature as a weather-conditioned demand modeling and simulator integration capability that preserves deterministic simulator inputs, adds producer-side demand workflows, supports stochastic non-thermal electric load and cooling demand, allows local electric cooling and district cooling serving paths, avoids double counting, keeps blackout semantics simulator-side, and keeps the first release cooling-only."

## Purpose *(mandatory)*

Add a unified-library demand capability that fits, persists, reloads, and
samples weather-conditioned demand traces for simulator use while preserving
the current deterministic simulator path. The feature separates producer-side
demand modeling from simulator-side execution so Open Energy Lab can grow from
weather-driven PV scenarios toward demand-aware cooling studies without mixing
artifact concerns into simulator core behavior.

The outcome is a first-release demand workflow that models both stochastic
non-thermal electric demand and stochastic cooling demand in refrigeration
tons, then adapts those traces into simulator scenarios that can compare local
electric cooling against district cooling without double counting
weather-driven HVAC effects.

## Clarifications

### Session 2026-06-15

- Q: Should the next feature be framed as stochastic load only or as a broader demand capability? → A: Frame it as weather-conditioned demand modeling with producer-side demand workflows and simulator-side demand consumers.
- Q: Should weather-conditioned electrical demand and explicit cooling demand be allowed in the same feature? → A: Yes, but the specification must make double counting impossible by keeping non-thermal electric demand and cooling demand as separate outputs.
- Q: Should thermal demand be folded into the existing deterministic electric load component? → A: No. Deterministic electric load remains a simulator-side electric concept; cooling demand is a separate thermal concept.
- Q: Should the first release include heating demand? → A: No. The implemented scope is cooling only, while heating remains an extension point.
- Q: Should the new producer package be named `load` or `demand`? → A: Prefer `demand` on the producer side because the feature covers electric and thermal demand, while preserving `load` terminology for simulator-side electric load consumption where appropriate.
- Q: Should weather and demand be merged into one joint artifact in the first stable release? → A: No. Weather remains the producer of weather traces, demand consumes weather traces for fitting or sampling semantics, and the simulator consumes both.
- Q: In the first release, can one scenario split cooling demand across local electric cooling and district cooling? → A: No. Each scenario chooses exactly one cooling service path: either local electric cooling or district cooling.
- Q: What unit and serving rule should the first release use for cooling demand? → A: Represent cooling demand in refrigeration tons (`RT`). Local electric cooling converts `RT` into site electric `kW` using a source-specific conversion factor, while district cooling serves the `RT` demand directly without adding site electric load.
- Q: How should district cooling affect first-release settlement? → A: District cooling uses its own deterministic tariff based on served cooling demand in `RT`.
- Q: What historical training data should the first-release cooling-demand fit require? → A: Require an explicit historical cooling-demand series in `RT` for fitting.
- Q: In the first release, how should paired weather and demand scenario families coordinate reproducibility seeds? → A: Use one shared paired-family seed, then derive weather and demand scenario seeds deterministically from it.

## Scope Classification *(mandatory)*

- **Feature type**: Migration plus new library capability
- **Target surface**: Public library demand API, persisted demand artifact,
  and simulator integration contract for paired weather-and-demand scenario
  families
- **Legacy reference paths**:
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
  - `legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb`
  - `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`
- **New-code location**:
  - `src/open_energy_lab/demand`
  - `src/open_energy_lab/simulator`
  - matching validation under `tests/unit`, `tests/integration`, and
    `tests/fixtures` as needed

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fit and Reload Weather-Conditioned Demand Artifacts (Priority: P1)

As a library user, I need to fit and later reload an offline demand artifact
that produces weather-conditioned demand traces so that I can study electric
and cooling demand variability without repeating a full preprocessing workflow
for every experiment.

**Why this priority**: Without a persisted demand artifact, the capability is
not reusable, reproducible, or aligned with the producer/consumer boundary
established by the stochastic weather feature.

**Independent Test**: A reviewer can load deterministic historical demand plus
aligned canonical weather fixtures, fit a demand artifact, reload it later
without network access, and verify that the artifact preserves explicit
non-thermal electric and cooling-demand outputs plus the metadata required for
later offline sampling.

**Acceptance Scenarios**:

1. **Given** aligned historical demand and canonical weather fixtures,
   **When** the demand fit workflow is executed, **Then** it produces a
   versioned demand artifact that can later be reloaded offline for sampling.
   The fitting inputs include an explicit historical cooling-demand series in
   `RT` rather than requiring decomposition from total electric load.
2. **Given** a persisted demand artifact, **When** it is reloaded offline,
   **Then** it preserves schema compatibility behavior, timestep locking,
   required weather drivers, and explicit non-thermal electric and cooling
   outputs for later paired demand sampling.

---

### User Story 2 - Sample Paired Weather-Conditioned Demand Families (Priority: P2)

As a researcher, I need to load a persisted demand artifact and an aligned
sampled weather family to generate reproducible paired demand scenarios so
that I can study demand variability without refitting for every experiment.

**Why this priority**: Sampling is the reusable stochastic interface between
persisted producer-side artifacts and simulator-side demand consumers.

**Independent Test**: A reviewer can load committed weather and demand
artifacts, request at least 10 paired demand scenarios for a positive horizon,
rerun the same request with the same paired-family seed, and verify identical
scenario ordering plus identical per-step weather and demand outputs.

**Acceptance Scenarios**:

1. **Given** a persisted demand artifact, an aligned sampled weather family, a
   shared paired-family seed, and a requested horizon, **When** demand
   sampling is performed, **Then** it returns reproducible sampled traces for
   both non-thermal electric demand and cooling demand in `RT` with aligned
   timesteps, distinct scenario indices, and deterministic seed derivation
   from one shared paired-family seed.
2. **Given** the same demand artifact, the same weather family, and the same
   paired sampling request, **When** sampling is repeated, **Then** it
   reproduces the same scenario ordering and the same per-step weather and
   demand outputs.

---

### User Story 3 - Evaluate Cooling Service Paths While Preserving Deterministic and Import-Light Boundaries (Priority: P3)

As a simulator maintainer and library consumer, I need paired weather and
demand traces to drive cooling-aware scenario families without making the core
simulator heavier or breaking the deterministic debugging path.

**Why this priority**: The feature only provides end-to-end value if sampled
demand can drive cooling-aware simulator comparisons while preserving existing
deterministic and import-light library boundaries.

**Independent Test**: A reviewer can evaluate one scenario family using the
same base simulator configuration for local electric cooling and district
cooling, verify explicit cooling-service balance and settlement outputs,
confirm blackout intervals remain simulator-side only, and continue to run the
existing deterministic simulator inputs and core imports without any demand
artifact.

**Acceptance Scenarios**:

1. **Given** sampled non-thermal electric demand, sampled cooling demand in
   `RT`, and a simulator configuration that uses local electric cooling,
   **When** a scenario family is evaluated, **Then** the simulator derives
   local cooling electric demand in site electric `kW` from the cooling demand
   using the local-cooling conversion factor and includes it in total site
   electric load.
2. **Given** the same sampled cooling demand and a simulator configuration
   that uses district cooling, **When** the family is evaluated, **Then**
   district cooling satisfies the served cooling demand directly in `RT`, that
   served portion does not appear as site electric load, and settlement uses a
   deterministic district-cooling tariff based on served `RT`.
3. **Given** a first-release cooling-aware scenario, **When** the simulator
   configuration is validated, **Then** it accepts exactly one cooling service
   path for that scenario, rejects mixed local-plus-district service within
   the same scenario, rejects district cooling without a deterministic tariff,
   and rejects district cooling configured to serve more thermal demand than is
   present in a timestep.
4. **Given** a cooling-aware family evaluation with blackout intervals,
   **When** the family is evaluated, **Then** blackout constraints remain
   simulator-side grid-service behavior and do not modify the sampled demand
   traces or fitted demand artifact contents.
5. **Given** the existing deterministic simulator inputs and the baseline
   local environment, **When** they are evaluated and
   `import open_energy_lab`, `import open_energy_lab.demand`, and
   `import open_energy_lab.simulator` are validated, **Then** the current
   deterministic path continues to work as a debugging and regression surface
   and routine imports do not require heavy building, optimization, notebook,
   GPU, or cluster workflows.

### Edge Cases

- The sampled non-thermal electric demand already includes weather-driven HVAC
  effects while explicit cooling demand is also present; the feature must
  reject or prevent that double-counting configuration.
- A demand artifact is sampled against a weather timestep that does not match
  the artifact contract.
- Demand fitting is attempted without an explicit historical cooling-demand
  series in `RT`.
- Cooling demand exists for a timestep but neither local electric cooling nor
  district cooling is configured to serve it; the simulator must represent the
  resulting unserved cooling demand explicitly rather than silently discarding
  it.
- Local electric cooling is configured with an invalid or unsupported
  efficiency description for the active scenario horizon.
- District cooling is configured to serve more thermal demand than is present
  in a timestep.
- District cooling is configured without a deterministic tariff even though the
  scenario requests district-cooling settlement.
- Weather sampling and demand sampling use different family seeds or scenario
  orderings than the paired family contract expects.
- Review-time validation is attempted without optional live data sources,
  CityLearn installs, solver licenses, GPU/SLURM access, or building datasets;
  the default validation path must remain offline and fixture-backed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST add a producer-side demand capability that fits,
  persists, reloads, and samples weather-conditioned demand traces without
  changing simulator execution ownership.
- **FR-002**: The feature MUST preserve the current deterministic simulator
  electric-load path as a supported debugging and regression surface.
- **FR-003**: The producer-side demand capability MUST model two first-release
  outputs: non-thermal electric demand and cooling demand in refrigeration
  tons (`RT`).
- **FR-004**: The feature MUST keep non-thermal electric demand and cooling
  demand as explicitly separate concepts throughout fitting, artifact loading,
  sampling, and simulator integration.
- **FR-005**: The feature MUST define the first-release public boundary for
  total site electric demand as non-thermal electric demand plus any locally
  served electric cooling demand.
- **FR-006**: The feature MUST define district cooling as a cooling serving
  path that satisfies cooling demand directly in `RT`, MUST NOT count served
  district cooling as site electric load in the first release, and MUST settle
  served district cooling through a deterministic tariff based on served
  cooling demand in `RT`.
- **FR-006a**: The first release MUST allow exactly one cooling service path
  per scenario: local electric cooling or district cooling. Mixed service
  within the same scenario is out of scope.
- **FR-007**: The feature MUST define how locally served electric cooling is
  derived from cooling demand in `RT` using one documented source-specific
  conversion factor that is stable and reproducible for the first release, and
  MUST treat that derived local electric cooling as site electric `kW`.
- **FR-008**: The feature MUST make double counting impossible by contract:
  weather-driven HVAC effects MUST NOT be hidden inside sampled non-thermal
  electric demand when explicit cooling demand is present for the same modeled
  service.
- **FR-009**: The demand capability MUST consume canonical weather inputs
  produced by the weather feature, but the first stable release MUST NOT merge
  weather and demand into one joint persisted artifact.
- **FR-009a**: The first-release cooling-demand fit workflow MUST require an
  explicit historical cooling-demand series in `RT` and MUST NOT require the
  library to decompose total electric-load history into cooling and
  non-thermal components.
- **FR-010**: The feature MUST support offline, fixture-backed fitting and
  sampling validation by default and MUST NOT require routine live external
  data fetches during review.
- **FR-011**: The feature MUST define reproducibility inputs for demand
  fitting, artifact versioning, family seeds, scenario ordering, timestep
  alignment, and validation tolerances.
- **FR-011a**: The first release MUST define one shared paired-family seed for
  weather and demand scenario families and MUST derive weather-side and
  demand-side scenario seeds deterministically from that shared seed plus
  scenario index.
- **FR-012**: The feature MUST support arbitrary positive sampling horizons
  rather than only full-day outputs.
- **FR-013**: The simulator integration MUST support paired weather and demand
  scenario-family evaluation using aligned scenario indices and one common time
  grid.
- **FR-014**: The simulator integration MUST preserve blackout semantics as a
  simulator-side concern separate from demand fitting and demand artifact
  contents.
- **FR-015**: The simulator integration MUST represent cooling-demand service
  balance explicitly, including served cooling demand in `RT`, any derived
  local cooling electric demand in `kW`, and any unserved cooling demand when
  full service is not available.
- **FR-016**: The feature MUST define stable summary outputs for paired
  scenario-family evaluation, including load-related outputs and
  district-cooling settlement outputs needed to compare electric and
  district-cooling cases.
- **FR-017**: The feature MUST require future implementation work to cite
  exact legacy files actually used as migration evidence and to distinguish
  migration-grade behavior from conceptual-only references.
- **FR-018**: The feature MUST identify which legacy behavior is preserved,
  which behavior is improved, and which thermal or HVAC behavior is explicitly
  treated as a new library capability rather than legacy parity.
- **FR-019**: The feature MUST keep unconditional core imports lightweight and
  MUST NOT require CityLearn, building simulators, solver-backed optimization,
  notebook tooling, W&B, GPU or SLURM tooling, or runtime `legacy/*` imports
  for the base library path.
- **FR-020**: The feature MUST keep first-release scope limited to cooling
  demand only and MUST treat heating demand as a future extension point.
- **FR-021**: The feature MUST keep indoor temperature state, comfort
  penalties, building-envelope dynamics, detailed HVAC equipment libraries,
  district-network hydraulics, district plant dispatch, and fully joint
  weather-demand artifact fitting out of scope for the first release.
- **FR-022**: The feature MUST define the public API maturity expectation for
  the new demand surface, including which exported concrete types remain
  experimental even though `open_energy_lab.demand` and
  `open_energy_lab.simulator` are stable package locations.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**:
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
  - `legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb`
  - `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`
- **Behavior to preserve**: Weather-sensitive demand direction where it is
  documented clearly enough to motivate conditioning on outdoor weather, plus
  the distinction between non-shiftable electric load and explicit thermal
  loads where legacy material makes that distinction visible.
- **Behavior to improve or drop**: Notebook-only assumptions, bundled thermal
  loads hidden inside non-shiftable load, implicit building-state dynamics,
  CityLearn-shaped runtime coupling, and any undocumented HVAC semantics that
  cannot be validated with deterministic fixtures or documented equations.
- **Parity evidence**: Deterministic fixtures for fitted-demand artifact
  schema, sampled demand family schema, paired weather-and-demand family
  evaluation, energy and thermal service accounting invariants, and import
  boundary checks. Full parity to CityLearn or notebook workflows is not
  required for this feature.

### Key Entities *(include if feature involves data or API design)*

- **Demand Artifact**: Persisted producer-side demand model for one fixed
  timestep, including version metadata, provenance, supported output modes, and
  enough fitted information to sample demand families offline.
- **Demand Sampling Request**: Caller-provided request describing scenario
  count, positive horizon length, one shared paired-family seed, and the
  weather reference used for paired demand sampling.
- **Sampled Demand Trace**: One scenario-indexed demand trace containing
  aligned non-thermal electric demand, cooling demand in `RT`, timestep
  metadata, and a derived identity for reproducibility.
- **Demand Scenario Family**: Ordered collection of sampled demand traces that
  share one derived seed lineage, one timestep, one horizon length, and one
  sampling contract.
- **Cooling Service Configuration**: Simulator-side configuration describing
  whether cooling demand in `RT` is served locally with electric cooling or
  served by district cooling for one scenario, along with the applicable
  source-specific conversion factor.
- **Cooling Service Result**: Scenario-evaluation output describing local
  cooling electric demand in `kW`, district cooling served demand in `RT`,
  district-cooling settlement, and any unserved cooling demand for each
  timestep.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Existing `open_energy_lab` core plus whatever minimal
  functionality is required to load, validate, and sample demand artifacts in
  the base library environment.
- **Optional dependencies**: Any heavier fitting-time data-processing or
  research dependencies that are not required for deterministic simulator
  imports or offline artifact loading.
- **External services**: None for the routine review path.
- **Hardware assumptions**: CPU-only local validation for the first release;
  no GPU or SLURM requirement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can fit one fixture-backed demand artifact, reload it
  offline, and sample at least 10 paired demand scenarios for a requested
  positive horizon without using live services.
- **SC-002**: Repeating the same paired weather-and-demand sampling request
  with the same seeds and configuration reproduces the same scenario ordering
  and the same per-step weather and demand outputs.
- **SC-003**: A reviewer can compare local electric cooling and district
  cooling on the same sampled cooling-demand family and verify that served
  district cooling in `RT` does not appear in site electric demand while
  locally served cooling produces derived site electric `kW`, and that
  district cooling uses its own deterministic tariff.
- **SC-004**: Validation fixtures and scenario-family checks detect no thermal
  or electric double counting in the supported first-release configurations.
- **SC-005**: The existing deterministic simulator path remains usable without
  a demand artifact and the base library imports continue to succeed without
  building-simulation, solver, notebook, GPU, or cluster dependencies.

## Assumptions

- Primary users are researchers and maintainers who want a Python library
  boundary for weather-aware demand modeling and simulator studies rather than
  a notebook-only workflow.
- `legacy/old_tpm` and `legacy/fed_trpo` remain reference-only unless a later
  feature explicitly migrates additional validated behavior.
- The first release can treat historical demand inputs and canonical weather
  inputs as aligned fixture-backed records rather than requiring live utility
  or building data integrations.
- Historical cooling-demand training data is assumed to be available as an
  explicit aligned series in `RT` for first-release fitting workflows.
- Paired weather-and-demand sampling is assumed to use one shared top-level
  family seed rather than independently chosen top-level weather and demand
  seeds.
- Cooling demand is the only explicit thermal-demand mode in scope for this
  feature; heating demand can be added later without redefining the producer/
  consumer boundary.
- Local electric cooling can be represented by one documented reproducible
  source-specific conversion factor from `RT` to site electric `kW` in the
  first release without requiring full HVAC or indoor comfort dynamics.
- District cooling in the first release is a service-path accounting concept,
  not a full district network or plant simulation, but it does carry a
  deterministic settlement path based on served `RT`.
- Some conceptual thermal-load direction exists in legacy notebooks, but the
  first stable demand feature will rely on new fixture-backed library contracts
  rather than notebook parity.
