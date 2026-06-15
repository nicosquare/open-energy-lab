# Research: Stochastic Weather Generation And Simulator Integration

## Decision 1: Create a separate `open_energy_lab.weather` package and keep the simulator as consumer

**Decision**: The stable public weather workflow will live under
`open_energy_lab.weather`, while `open_energy_lab.simulator` remains the sole
owner of execution semantics and consumes either deterministic weather inputs
or sampled weather families.

**Rationale**: The requested workflow includes fetch, fit, artifact
persistence, and offline sampling. Those concerns are broader than the current
deterministic simulator weather component and would make simulator ownership
unclear if merged into `open_energy_lab.simulator.weather`. A separate package
keeps the simulator focused on energy-flow evaluation and makes the weather
workflow reusable outside one scenario type.

**Alternatives considered**:

- Expand `open_energy_lab.simulator.weather` to own fetch and fitting:
  rejected because it blurs simulator execution ownership.
- Put stochastic weather under `open_energy_lab.experimental` first: rejected
  because the spec requires a stable first-release workflow from fit through
  offline sampling and simulator consumption.

## Decision 2: Use a PVGIS-backed TMY fetch workflow as part of the shipped weather environment

**Decision**: The fit/fetch workflow will follow the legacy PVGIS direction and
use a library-owned TMY fetch adapter around `pvlib.iotools.get_pvgis_tmy`,
with `pvlib`, `pandas`, and `timezonefinder` treated as part of the shipped
weather environment rather than a separate optional install.

**Rationale**: The legacy weather subsystem already uses `pvlib` for PVGIS TMY
fetch, which provides direct evidence for the requested geolocation-driven TMY
workflow. The feature also requires offline artifact loading and sampling,
which means network-backed fetch tooling must not become a prerequisite for
ordinary simulator imports or for using a previously fitted artifact.

**Alternatives considered**:

- Call the PVGIS HTTP API directly without `pvlib`: rejected because it adds
  avoidable parsing and provider-format handling in the first release.
- Require live fetch tooling for all sampling workflows: rejected because the
  spec explicitly requires offline artifact reuse.
- Keep the live-fit stack as a separate optional install: rejected because it
  weakens the first-class status of the shipped stochastic weather capability.

## Decision 3: Normalize all supported variables into one canonical schema in local civil time

**Decision**: The first release will normalize all ten supported weather
variables into one canonical library schema, convert the fetched TMY data to
location-local civil time for fitting and sampling semantics, and fail fast if
any required canonical field cannot be mapped.

**Rationale**: The clarified spec rejected partial artifacts and fixed the time
basis to local civil time. A single canonical schema keeps the artifact and
simulator contracts stable, preserves the full supported variable set from
`src/open_energy_lab/simulator/_weather_schema.py`, and removes the legacy MVP
split between included and merely deferred runtime fields.

**Alternatives considered**:

- Keep provider-specific labels as the runtime contract: rejected because it
  weakens schema stability.
- Keep fitting and sampling in raw UTC: rejected because daily weather
  structure is easier to learn and validate in local time.
- Permit partial artifacts when fields are missing: rejected by clarification
  because it would complicate simulator and validation logic.

## Decision 4: Use one joint daily-block multivariate weather model at a fixed timestep

**Decision**: The stable first-release weather model will fit one joint daily
multivariate model over all canonical variables at one fixed timestep per
artifact, sample full local-day blocks, and trim the concatenated output to the
requested `num_steps`.

**Rationale**: The spec explicitly prefers preserving cross-variable and
cross-time relationships over preserving the legacy separate-per-variable
training structure. A joint daily-block model keeps relationships between
temperature, irradiance, humidity, wind, and pressure explicit in one fitted
surface while still following the legacy daily-profile direction closely enough
to be explainable and testable.

**Alternatives considered**:

- Preserve one independent model per variable: rejected because it does not
  make realistic cross-variable behavior the stable contract.
- Build a more complex sequential model such as a hidden-state or
  autoregressive architecture: rejected for the first release because it adds
  modeling complexity without stronger validation evidence yet.
- Support mixed timestep sampling from one artifact: rejected by clarification
  because it weakens reproducibility and schema clarity.

## Decision 5: Model cloud behavior as a shared multi-step irradiance-event overlay

**Decision**: The stable sampling workflow will overlay a shared cloud-event
model on top of the joint base sample for irradiance variables. The cloud-event
layer will model contiguous attenuation events with local-time start behavior,
duration, and attenuation magnitude rather than using independent per-step
drops.

**Rationale**: The legacy enhanced model and drop analysis provide the right
direction, but the clarified spec requires ordinary cloud or irradiance
attenuation events that span multiple steps. A shared event layer over GHI,
DNI, and DHI better preserves realistic co-movement than legacy per-step
Bernoulli drops and still keeps the model simple enough to validate with
documented stochastic checks.

**Alternatives considered**:

- No dedicated cloud-event layer, rely only on the base joint model: rejected
  because cloud events are a named feature requirement.
- Preserve the legacy independent per-step drop overlay: rejected because it
  does not model multi-step event duration clearly enough.

## Decision 6: Persist fitted models as versioned JSON artifacts with fail-fast loading

**Decision**: The first release will use a versioned JSON artifact for fitted
weather models, including provenance, timestep, local-time basis metadata, base
model parameters, and cloud-event parameters. Artifact loading will accept only
explicitly supported schema versions and fail fast on unsupported mismatches.

**Rationale**: The repo already uses JSON fixtures heavily, and the clarified
spec prioritizes deterministic schema validation and explicit version
compatibility rules. JSON keeps the artifact inspectable and easy to fixture for
tests, while fail-fast loading avoids promising migration behavior before the
artifact schema has stabilized.

**Alternatives considered**:

- Use pickle or another opaque Python-native format: rejected because it is
  harder to review, less portable, and less suitable for committed fixture
  evidence.
- Use automatic artifact migration on load: rejected because the spec now
  requires explicit support and fail-fast behavior for unsupported versions.

## Decision 7: Make offline sampling reproducible from one family seed plus scenario index

**Decision**: The stable sampling contract will take one family-level seed and
derive each scenario instance deterministically from that seed plus scenario
index and ordering.

**Rationale**: This satisfies the clarified reproducibility requirement without
forcing callers or tests to manage long lists of per-scenario seeds. It also
aligns naturally with the stable scenario-family result surface and makes exact
family reruns straightforward.

**Alternatives considered**:

- Require an explicit seed for every scenario instance: rejected because it is
  cumbersome for common family workflows.
- Generate random scenario seeds implicitly: rejected because it weakens
  reproducibility.

## Decision 8: Keep blackouts outside the fitted weather artifact and model them as grid outages

**Decision**: Blackout behavior will remain caller-configured simulator-side
input, not fitted from TMY data. In the first release, a blackout means grid
outage only: grid import and export are disabled, local PV and battery may
continue serving load, and any remaining shortfall becomes explicit unmet load.

**Rationale**: TMY weather data does not provide outage evidence, and the spec
now explicitly separates blackout semantics from weather attenuation. Treating
blackouts as simulator-side configuration preserves clear ownership, keeps the
weather artifact focused on weather behavior, and produces a concrete resilience
surface for validation.

**Alternatives considered**:

- Fit or calibrate blackouts from weather artifacts: rejected because it would
  create a false coupling between weather data and outage semantics.
- Treat blackouts as full site outages: rejected because it narrows the value
  of the simulator integration without being required by the spec.

## Decision 9: Ship stable scenario-family results with bounded built-in summaries

**Decision**: The stable simulator family-result surface will return
per-scenario traces plus built-in min/mean/max/5th/50th/95th summaries over
documented core simulator outputs only: PV generation, net-grid power, unmet
load, and settlement metrics.

**Rationale**: The clarifications promoted family summaries into the stable
surface but limited their scope to decision-relevant simulator outputs. This
gives downstream consumers useful built-in aggregation without forcing the
simulator contract to summarize every numeric field or raw weather variable.

**Alternatives considered**:

- Return only per-scenario traces and defer summaries entirely: rejected by
  clarification.
- Summarize every numeric simulator and weather field: rejected because it
  makes the stable contract too broad for the first release.

## Decision 10: Classify dependencies to keep fit/fetch isolated from offline artifact use

**Decision**: Dependency boundaries for the feature will be:

- `core` for the weather capability:
  - Python standard library
  - `numpy`
  - existing `open_energy_lab.simulator` modules used during integration
- `optional`:
  - `pytest` for validation
- `external-service-backed` and isolated to the fit/fetch workflow:
  - `pvlib`
  - `pandas`
  - `timezonefinder`
- `legacy-only`:
  - all cited legacy weather and simulator reference files

**Rationale**: The feature needs array math for fitting and offline sampling,
but base library imports still need to avoid network, notebook, solver, and RL
stacks. This split keeps the stable weather capability implementable without
reintroducing the heavy dependency families the constitution warns about.

**Alternatives considered**:

- Keep every weather dependency optional, including `numpy`: rejected because
  offline sampling is part of the stable workflow.
- Make fetch and normalization dependencies part of the base import path:
  rejected because it would violate the import-light and offline-use goals.
