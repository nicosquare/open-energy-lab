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

## Decision 5: Require SPFlow and Pyomo while retaining lazy imports

**Decision**: Fitting and solver-facing model assembly will use SPFlow and
Pyomo as the canonical backends inside `open_energy_lab.tpm` and
`open_energy_lab.planning`. Both are installed by default, while package roots
remain import-light through lazy workflow-boundary adapters.

**Rationale**: The constitution and current repo tests already enforce import
boundaries. Required installation and lazy import solve different problems:
SPFlow and Pyomo are fundamental to the feature, while deferred loading avoids
cost and side effects for weather, demand, and simulator-only users. Required
real-backend CI prevents lazy loading from hiding an incompatible installation.

**Alternatives considered**:

- Import SPFlow and Pyomo unconditionally at package-root import time: rejected
  because installation policy does not require eager loading and the library
  retains an import-light boundary.
- Put the backends in an opt-in extra: rejected because the clarified feature
  contract requires them in every standard project installation.
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
with the selected first-release contract. A finite all-categorical planning
domain may evaluate the compiled conditional graph exactly and link those
probabilities to binary one-hot decisions; this remains a solver-driven MILP
consumer of the canonical compiler rather than a second empirical backend.

**Alternatives considered**:

- Lower-tangent canonicalization: rejected by clarification.
- Exact nonlinear optimization: rejected because the requested first release
  is an MILP planning surface.
- Pre-enumerated design catalogs only: rejected because the spec requires
  direct typed decision-variable optimization.

## Decision 7: Require a real HiGHS solve while preserving assembly-only use

**Decision**: `open_energy_lab.planning` will first guarantee deterministic
problem-definition validation and model assembly, and the standard workflow and
routine CI will execute the model with Pyomo's `highs` solver backed by the
required `highspy` package. Callers may still inspect assembly without solving.

**Rationale**: HiGHS provides a license-free, pip-installable solver and Pyomo
supports it directly. This makes end-to-end solve validation routine without
requiring Gurobi. Assembly-only inspection remains useful, but it is no longer
a substitute for real solver evidence.

**Alternatives considered**:

- Keep every solver optional: rejected because it previously allowed the main
  planning workflow to pass without being exercised end to end.
- Require Gurobi in routine CI: rejected because licensing and external
  configuration would make the default validation path non-portable.
- Expose planning as solver-specific scripts only: rejected because the
  feature asks for a reusable library API.

## Decision 8: Reuse existing demand and weather families as the canonical export inputs

**Status**: Superseded for scalable studies by Decision 12 after the original
export, dataset, and TPM contracts stabilized. It remains the contract for the
single-family export workflow.

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

## Decision 10: Combine deterministic fixtures with required real-backend CI

**Decision**: Routine validation will use committed dataset-export fixtures,
TPM metadata fixtures, query fixtures, and assembly fixtures, and will also run
a real SPFlow fit/reload/query cycle plus a real Pyomo/HiGHS solve. Gurobi and
legacy-runtime parity remain optional follow-up checks.

**Rationale**: Fixtures provide reproducibility but fake or empirical paths do
not prove the canonical backends work. The required dependencies and HiGHS
allow both forms of evidence offline and without a commercial license.

**Alternatives considered**:

- Treat fake backends as sufficient integration evidence: rejected because it
  allowed implementation drift at the actual SPFlow/Pyomo boundary.
- Use only smoke tests without fixtures: rejected because the feature is a
  migration and needs deterministic evidence.

## Decision 11: Port validated behavior to current SPFlow instead of constraining Python

**Decision**: Target `spflow==1.1.0` as the initial current backend,
`pyomo==6.10.1`, and `highspy==1.15.1`, retaining the project Python floor of
3.11 without adopting the legacy SPFlow line's `<3.13` constraint. Use Pyomo
`SolverFactory("highs")` as the canonical solver interface. Widen initial pins
only after real-backend CI proves compatible endpoints.

**Rationale**: SPFlow 1.1 is the current supported PyTorch-based rewrite and
declares Python 3.10+. Its API provides current structure learning,
`model.log_likelihood(...)`, missing-value marginalization, and structural
`model.marginalize(...)`. Legacy models are explicitly incompatible and must
be rebuilt, so the migration preserves validated mathematical behavior and
artifact contracts rather than serialized legacy objects. This cost is
preferred to constraining the unified library to an obsolete backend.

**Migration mapping to validate**:

- legacy `learn_mspn(...)` maps to current `spflow.learn.learn_spn(...)` with
  PyTorch tensors and explicit leaf modules/scopes
- legacy free-function log likelihood maps to
  `model.log_likelihood(...)`
- query marginalization maps either to NaN evidence for likelihood evaluation
  or `model.marginalize(...)` for a structurally marginalized circuit
- legacy node classes and traversal cannot be assumed compatible; the
  current-SPFlow-to-piecewise-MIO compiler requires a deliberate adapter over current modules and
  weights with parity fixtures for every supported node/leaf type
- legacy pickle payloads are migration inputs only; new artifacts persist a
  versioned current-backend payload and must be refitted

**Alternatives considered**:

- Pin pre-1.0 SPFlow and cap Python below 3.13: rejected by the clarified
  preference to keep modern Python support and bear the porting cost.
- Support both legacy and current SPFlow in production: rejected because it
  doubles the backend and artifact compatibility surface; legacy behavior
  remains parity evidence instead.
- Use `appsi_highs` canonically: rejected because the workflow builds and
  solves rather than repeatedly updating one persistent model; it remains a
  non-canonical compatibility option.

## Decision 12: Add a resumable discrete study runner with common random samples

**Decision**: Treat battery and solar products as categorical equipment
options, simulate their Cartesian product with identical absolute-indexed
weather/demand/outage samples, and persist results in deterministic shards.

**Rationale**: Direct caller metadata can diverge from the physical scenario,
and one embedded JSON payload does not support large or resumable studies.
Simulator-derived option metadata plus common random numbers provides fair,
reproducible design comparisons.

## Decision 13: Keep optimization solver-driven and validate the selected point

**Decision**: Encode equipment choices and their installed costs directly in
the SPN MIO, solve with HiGHS, and compare the selected design's probability
with native SPFlow. When every decision is categorical, evaluate each finite
joint assignment against the compiled conditional SPN and link those exact
risk coefficients to the decision one-hot variables.

**Rationale**: Exhaustive evaluation is useful for generating training data
but must not replace the encoded optimization. Selected-point validation is an
independent approximation check with bounded cost.

## Decision 14: Cache canonical PVGIS data separately and fit without refetching

**Decision**: The configurable autonomy notebook uses the explicit PVGIS 5.3
endpoint, persists request/cache provenance with the canonical hourly table,
and calls a canonical-dataset weather fit entry point.

**Rationale**: A separate cache makes the external-data boundary reviewable and
lets the producer fit exactly the records that were fetched. Failure is
explicit when neither cache nor network is available; a fixture cannot be
mistaken for Abu Dhabi evidence.

## Decision 15: Select on validation and gate recommendations on final test

**Decision**: Fit real SPFlow candidates on training data, rank only compilable
candidates by validation Brier score and node-count tie-break, then use an
independent final test for calibration and a conservative selected-design risk
bound.

**Rationale**: Compiler parity establishes encoding fidelity, not statistical
calibration. Separating candidate selection from final evidence prevents the
same samples from selecting and approving the model.

## Decision 16: Preserve general piecewise encoding and specialize finite categorical planning

**Decision**: Keep the canonical current-SPFlow compiler and general piecewise
Pyomo encoding for continuous or mixed decision domains. For finite
all-categorical battery/solar domains, use an exact lookup evaluated from the
compiled conditional graph and record `exact-categorical-lookup` in solver
metadata.

**Rationale**: The generic disjunctive piecewise formulation can be needlessly
large and numerically fragile when every feasible decision already has a
finite categorical domain. Exact compiled-graph coefficients preserve native
probability parity, remain independent from empirical study rows, and give
HiGHS a small linear chance constraint without changing TPM ownership.

**Alternatives considered**:

- Enumerate empirical event-rate candidates: rejected because training rows
  are evidence for fitting, not the optimization model.
- Replace the general piecewise formulation: rejected because continuous and
  mixed typed decisions still require it.
- Load a time-limited incumbent as optimal: rejected because recommendation
  requires a proved optimal solution and deterministic native verification.
