# Research: Weather-Conditioned Demand Modeling And Simulator Integration

## Decision 1: Create a separate `open_energy_lab.demand` package and keep the simulator as consumer

**Decision**: The stable public demand workflow will live under
`open_energy_lab.demand`, while `open_energy_lab.simulator` remains the owner
of execution semantics and consumes either deterministic exogenous inputs or
paired sampled weather-and-demand families.

**Rationale**: The requested workflow includes aligned-history fitting,
artifact persistence, offline reloading, and stochastic sampling. Those
producer-side concerns are broader than the current deterministic simulator
`load` component and would blur simulator ownership if merged into
`open_energy_lab.simulator.load` or `scenario.py`. A separate package keeps
the demand workflow reusable outside one simulator path and matches the
producer/consumer boundary already established for weather.

**Alternatives considered**:

- Expand `open_energy_lab.simulator.load` to own fitting and sampling:
  rejected because it mixes simulator execution with artifact production.
- Add demand fitting under `open_energy_lab.weather`: rejected because weather
  and demand remain explicitly separate artifacts and producer surfaces.
- Put the first release under `open_energy_lab.experimental`: rejected because
  the spec requires a stable package location for the new demand capability.

## Decision 2: Require explicit aligned historical non-thermal electric demand, cooling demand in `RT`, and canonical weather

**Decision**: The first-release fit workflow will require three aligned inputs:
canonical weather history from the weather feature, explicit historical
non-thermal electric demand, and explicit historical cooling demand in `RT`.
The library will not decompose total electric load into thermal and
non-thermal components.

**Rationale**: The spec requires double counting to be impossible by contract
and already clarifies that cooling-demand fitting must require an explicit
historical cooling series in `RT`. Extending that discipline to non-thermal
electric demand preserves a clean accounting boundary and avoids silently
fitting thermal behavior into the wrong output.

**Alternatives considered**:

- Fit from total site electric load and infer cooling retrospectively:
  rejected because it would reintroduce ambiguous thermal content.
- Require only cooling history and infer non-thermal electric load from
  residual electric demand: rejected because the library would still be doing
  decomposition the spec avoids.
- Reuse notebook or CityLearn runtime state directly as training input:
  rejected because the first release must stay fixture-backed and import-light.

## Decision 3: Fit one dual-output, local-civil-time, weather-conditioned daily-block model with correlated residuals

**Decision**: The stable first-release demand artifact will fit one fixed-
timestep conditional model that produces two outputs, non-thermal electric
demand and cooling demand in `RT`, using local-civil-time weather-aligned
profiles, output-specific baseline response terms, and a shared residual model
that preserves cross-output correlation at the sampled-scenario level.

**Rationale**: The feature needs explicit weather conditioning, separate
electric and thermal outputs, and paired-family reproducibility without
committing to full building-state or HVAC dynamics. A dual-output conditional
daily-block model keeps the public contract interpretable and fixture-friendly
while still preserving meaningful co-movement between electrical and cooling
demand.

**Alternatives considered**:

- Fit two fully independent demand models: rejected because it weakens
  cross-output consistency.
- Fit one total-demand model and split outputs after sampling: rejected
  because it violates the explicit separation requirement.
- Adopt a full building-envelope or HVAC state model: rejected for the first
  release because it adds heavy assumptions and validation burden beyond the
  spec.

## Decision 4: Keep weather and demand artifacts separate and coordinate them with one shared paired-family seed

**Decision**: Weather and demand remain separate persisted artifacts. Demand
sampling will consume a weather-family reference or sampled weather traces and
the same shared paired-family seed used for the weather family, then derive
demand-side scenario seeds deterministically from that shared seed plus
scenario index.

**Rationale**: The clarified spec explicitly rejects a merged weather-demand
artifact while still requiring paired reproducibility. Separate artifacts keep
package ownership clean and allow demand behavior to evolve without changing
the weather artifact contract. Shared seed lineage preserves exact scenario
ordering and replay semantics across both producers.

**Alternatives considered**:

- Merge weather and demand into one joint artifact: rejected by clarification.
- Give weather and demand independent family seeds: rejected because it weakens
  paired reproducibility and scenario alignment.
- Hide seed derivation inside a simulator-only coordinator: rejected because
  the producer-side demand contract itself needs deterministic replay.

## Decision 5: Make cooling-service choice a simulator-side configuration with exactly one path per scenario

**Decision**: Each first-release cooling-aware simulator scenario will choose
exactly one cooling service path: local electric cooling or district cooling.
That choice is simulator-side configuration, not artifact content.

**Rationale**: The spec explicitly rejects mixed local-plus-district service
within one scenario and keeps blackout and service semantics on the simulator
side. Treating service choice as scenario configuration keeps the demand
artifact focused on sampled demand quantities rather than downstream delivery
mechanics.

**Alternatives considered**:

- Encode the cooling path into the demand artifact: rejected because service
  path is not a producer-side property of demand.
- Allow mixed local and district service in one scenario: rejected by
  clarification.
- Allow no configured service path for a cooling-aware scenario: rejected
  because the first-release validation contract should fail fast on incomplete
  scenario configuration.

## Decision 6: Represent local electric cooling as deterministic `kW`-per-`RT` conversion and district cooling as deterministic `RT` settlement

**Decision**: Local electric cooling will derive site electric demand from
cooling demand in `RT` using one documented source-specific conversion factor
expressed as `kW` per `RT`. District cooling will satisfy thermal demand
directly in `RT` and use a deterministic tariff expressed per served
`RT-hour`.

**Rationale**: This matches the clarified accounting boundary: locally served
cooling becomes site electric load, while district cooling remains a thermal
service with its own tariff path. Using explicit rate parameters preserves
reproducibility and avoids inventing richer HVAC or district-network models.

**Alternatives considered**:

- Model local electric cooling with dynamic COP curves or indoor-state
  feedback: rejected for first release because it introduces unvalidated HVAC
  complexity.
- Treat district cooling as an electric equivalent and fold it into site load:
  rejected because the spec explicitly disallows that accounting.
- Use per-step ad hoc conversion without a documented contract: rejected
  because it weakens reproducibility.

## Decision 7: Surface explicit cooling-service balance, including unserved cooling, in simulator results

**Decision**: The simulator result contract will include served cooling demand
in `RT`, derived local cooling electric demand in `kW` when applicable,
district-cooling settlement, and explicit unserved cooling demand whenever the
configured service path cannot fully serve the sampled thermal demand.

**Rationale**: The spec requires explicit service-balance reporting and warns
against silently discarding thermal demand. This result surface makes cooling
path comparison auditable and keeps unmet thermal demand as visible as unmet
electric load during blackouts.

**Alternatives considered**:

- Report only total site electric load and total settlement: rejected because
  it hides thermal-service behavior and unserved cooling.
- Silently cap or drop unsupported cooling demand: rejected because it defeats
  validation and comparison.

## Decision 8: Keep the new demand surface import-light and isolate heavy research dependencies

**Decision**: The new demand package root must remain import-light like
`open_energy_lab.weather` and `open_energy_lab.simulator`. Artifact loading,
sampling, and package imports must not require CityLearn, building simulation,
solver stacks, notebooks, W&B, or live services. Fit-time data alignment may
reuse lightweight processing already available in the base environment, but it
must stay outside ordinary imports.

**Rationale**: The constitution and current tests already enforce import-light
boundaries. This feature adds a new public package, so it must inherit the
same discipline rather than becoming the first place heavy research stacks
leak into the stable namespace.

**Alternatives considered**:

- Reuse CityLearn or notebook code directly inside the stable package:
  rejected because it violates dependency and runtime boundaries.
- Make demand fitting require live weather fetches during review: rejected
  because the review path must remain offline and fixture-backed.

## Decision 9: Keep `open_energy_lab.demand` as the stable package location while leaving concrete artifact-model internals experimental

**Decision**: The package root `open_energy_lab.demand` will be a stable
public location that exports the workflow entry points, but detailed concrete
artifact-model internals and helper dataclasses may remain experimental until
later validation promotes them explicitly.

**Rationale**: The spec requires a stable package location and also asks for a
documented maturity expectation. Matching the existing simulator package
pattern gives users a stable import root without overcommitting to every
internal type in the first release.

**Alternatives considered**:

- Mark the entire demand package experimental: rejected because the stable
  location is a requirement.
- Treat every concrete type as stable immediately: rejected because the first
  release is still a scoped migration with intentionally bounded evidence.

## Decision 10: Default validation stays offline and fixture-backed, with paired invariants instead of notebook parity

**Decision**: The routine validation path will use committed aligned-history,
artifact, sampled-family, and simulator fixtures. It will prioritize exact
schema checks, paired seed replay, cooling-service accounting invariants,
double-counting prevention, and import-boundary checks rather than parity to
CityLearn or notebook workflows.

**Rationale**: The legacy references are mostly conceptual notebook material,
not stable testable libraries. Fixture-backed contracts and paired invariants
provide credible evidence while staying compatible with the repo’s lightweight
review environment.

**Alternatives considered**:

- Require CityLearn or notebook execution for validation: rejected because it
  introduces optional dependencies and weakens repeatability.
- Claim parity to undocumented notebook behaviors: rejected because the spec
  only requires migration evidence where behavior is documented clearly enough
  to validate.
