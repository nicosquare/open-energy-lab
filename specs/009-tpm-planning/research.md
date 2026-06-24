# Research: TPM-Backed Planning And Simulator Dataset Export

## Decision 1: Put the dataset export workflow under `open_energy_lab.simulator`

**Decision**: The first-release planning-dataset export entry point will live
under `open_energy_lab.simulator` rather than `open_energy_lab.planning` or
`open_energy_lab.tpm`.

**Rationale**: The exported rows are derived directly from evaluated simulator
families and current simulator-side outputs such as weather traces,
site-electric demand, unmet load, and settlement fields. Keeping export
ownership simulator-side matches the existing package boundary in
`stochastic_weather.py` and `stochastic_demand.py`, and avoids turning the TPM
or planning packages into owners of simulation semantics.

**Alternatives considered**:

- Put export under `open_energy_lab.planning`: rejected because planning should
  consume stable datasets rather than own simulator flattening rules.
- Put export under `open_energy_lab.tpm`: rejected because TPM training should
  depend on a dataset contract, not define one.
- Keep export in notebooks: rejected because the feature requires a reusable
  library workflow.

## Decision 2: Treat planning datasets as versioned JSON-first artifacts with explicit provenance

**Decision**: The first release will persist one versioned planning dataset
artifact that stores flattened rows, schema metadata, export configuration,
shortfall-target metadata, and simulator provenance in JSON-compatible form.

**Rationale**: Existing weather and demand features already use reviewable
JSON artifacts and fixture-backed validation. A JSON-first contract keeps the
dataset diffable, easy to fixture, and compatible with offline review while
still allowing later convenience loaders to expose `pandas.DataFrame` views.

**Alternatives considered**:

- Parquet-only artifacts: rejected because they are less reviewable in
  committed fixtures.
- Pickle-only artifacts: rejected because pickle is opaque and unsafe as a
  stable interchange format.
- In-memory-only export: rejected because the feature requires persisted,
  reusable planning datasets.

## Decision 3: Canonicalize `shortfall` as a derived target from simulator unmet-load signals

**Decision**: The planning target `shortfall` will be derived from simulator
results as horizon-level unmet electric load energy divided by total horizon
electric load energy, with the exact timestep-weighted aggregation rule stored
in dataset metadata.

**Rationale**: The spec explicitly rejects notebook-owned semantics and fixes
`shortfall` as a library-owned target. The current simulator already exposes
`unmet_load_kw`, `site_electric_load_kw`, and `timestep_hours`, which are
sufficient to compute a stable energy-ratio target without introducing new
blackout logic into the TPM or planning packages.

**Alternatives considered**:

- Binary blackout labels only: rejected because the clarification explicitly
  preferred `shortfall` instead of legacy blackout labels.
- Cooling-service adequacy mixed into one target: rejected because the spec
  calls that ambiguous for the first release.
- Stepwise target vectors only: rejected because the first-release planning
  artifact is one explicit horizon-level target per row.

## Decision 4: Migrate typed feature classes closely, but replace pickle-only persistence with explicit contracts

**Decision**: The new `open_energy_lab.tpm` package will closely preserve the
legacy typed-feature concepts from `datahandler.py`, `feature.py`, and the
binary/categorical/contiguous/mixed feature classes, while replacing implicit
or pickle-only persistence assumptions with versioned artifact metadata.

**Rationale**: The legacy TPM feature typing is already structured and matches
the user’s stated migration goal. It is the right level to preserve closely,
provided the public library adds clear schema versions, provenance, and
documented input bounds instead of relying on opaque serialized state.

**Alternatives considered**:

- Rebuild feature typing from scratch: rejected because it discards validated
  legacy structure without need.
- Copy legacy files wholesale: rejected because the constitution requires
  selective migration and removal of duplicated or implicit behavior.
- Persist raw Python objects only: rejected because the new library needs
  explicit contracts and offline reviewable fixtures.

## Decision 5: Keep SPFlow and Pyomo integrations behind optional adapters

**Decision**: Fitting and solver-facing encoding will be exposed through
optional adapters inside `open_energy_lab.tpm` and `open_energy_lab.planning`,
while package roots remain import-light.

**Rationale**: The constitution and current repo tests already enforce import
boundaries. SPFlow and Pyomo are valid research dependencies for this feature,
but they should load only when callers explicitly fit TPMs or assemble solver
models that require them.

**Alternatives considered**:

- Make SPFlow and Pyomo base dependencies: rejected because it widens the core
  environment and breaks the current dependency policy.
- Skip library-owned fit/query support entirely: rejected because the feature
  explicitly includes fitting, reload, and query workflows.

## Decision 6: Use the legacy piecewise path as the canonical first-release solver-facing approximation

**Decision**: The first-release planning surface will standardize on a
piecewise SPN-to-MILP approximation derived from the legacy `encoding.py` and
`utils_tangent.py` direction, while explicitly not making lower-tangent
formulations canonical.

**Rationale**: The spec clarification already chose a canonical piecewise
path. The legacy codebase contains both the direct histogram/piecewise
machinery and tangent-oriented experiments, but only the piecewise path aligns
with the selected first-release contract.

**Alternatives considered**:

- Lower-tangent canonicalization: rejected by clarification.
- Exact nonlinear optimization: rejected because the requested first release
  is an MILP planning surface.
- Pre-enumerated design catalogs only: rejected because the spec requires
  direct typed decision-variable optimization.

## Decision 7: Define the first planning surface as problem assembly first, solve second

**Decision**: `open_energy_lab.planning` will first guarantee deterministic
problem-definition validation and model assembly, with actual solver execution
as an optional follow-up when supported solver backends are available.

**Rationale**: The feature must remain reviewable in environments without
commercial solvers or solver binaries. A strong assembly contract gives the
library a stable planning surface without forcing solver availability into the
routine review path.

**Alternatives considered**:

- Require a working solver in all environments: rejected because it conflicts
  with the offline default-validation requirement.
- Expose planning as solver-specific scripts only: rejected because the
  feature asks for a reusable library API.

## Decision 8: Reuse existing demand and weather families as the canonical export inputs

**Decision**: The initial dataset export contract will consume current
`DemandFamilyEvaluationResult` and `WeatherFamilyEvaluationResult` style data,
plus caller-provided design metadata and export configuration, instead of
introducing a new design-sweep simulator subsystem.

**Rationale**: The current library already has deterministic and family-based
simulator surfaces with aligned seeds, indices, and timesteps. Reusing them
keeps the planning slice incremental and compatible with the active
weather-demand feature.

**Alternatives considered**:

- Build a new exhaustive design-sweep simulator first: rejected because it
  expands scope before dataset and TPM contracts are stable.
- Depend on legacy data-generation notebooks: rejected because they are not a
  stable runtime surface.

## Decision 9: Keep planning scope to battery and solar decision variables in the first release

**Decision**: The first planning surface will expose direct battery and solar
decision variables only, even though the TPM feature schema may retain broader
typed-variable support.

**Rationale**: The spec explicitly narrows the first planning problem to
battery and solar, which keeps fixture design bounded and reduces ambiguity in
cost and feasibility contracts.

**Alternatives considered**:

- Include inverter and broader equipment decisions immediately: rejected by
  clarification.
- Narrow further to battery-only or solar-only: rejected because the spec
  explicitly calls for both in the first release.

## Decision 10: Make validation fixture-backed, with optional parity checks documented separately

**Decision**: Routine validation will use committed dataset-export fixtures,
TPM metadata fixtures, query fixtures, and assembly fixtures. Legacy tangent
tests and solver-backed checks remain documented as optional follow-up checks
when dependencies are available.

**Rationale**: This matches both the constitution and the repo’s current
working rules. It provides strong reproducibility evidence without requiring
commercial solvers or a locally configured SPFlow stack to review ordinary
changes.

**Alternatives considered**:

- Claim full legacy parity by default: rejected because optional dependencies
  make that unreliable for routine review.
- Use only smoke tests without fixtures: rejected because the feature is a
  migration and needs deterministic evidence.
