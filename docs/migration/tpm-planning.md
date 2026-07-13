# TPM-Backed Planning Migration Note

Status: User Story 1 simulator export and dataset reload, User Story 2 TPM fit, reload, and query, and User Story 3 planning assembly and optional solve with committed offline fixtures implemented

Spec `009-tpm-planning` now ships the simulator-owned planning-dataset export
slice under `open_energy_lab.simulator`, the persisted planning-dataset and
planning-assembly surface under `open_energy_lab.planning`, a stable TPM
fit/reload/query surface under `open_energy_lab.tpm`, and committed offline
fixtures for deterministic export replay, TPM artifact reload, planning
problem assembly, and optional solve review. The planning solve path remains
solver-optional in the default review flow, but it is no longer just a
reserved future boundary.

## Target Module Paths

- `src/open_energy_lab/simulator/planning_export.py`
- `src/open_energy_lab/tpm/__init__.py`
- `src/open_energy_lab/tpm/artifact.py`
- `src/open_energy_lab/tpm/data.py`
- `src/open_energy_lab/tpm/features.py`
- `src/open_energy_lab/tpm/fit.py`
- `src/open_energy_lab/tpm/query.py`
- `src/open_energy_lab/tpm/piecewise.py`
- `src/open_energy_lab/tpm/optional_spflow.py`
- `src/open_energy_lab/planning/__init__.py`
- `src/open_energy_lab/planning/dataset.py`
- `src/open_energy_lab/planning/problem.py`
- `src/open_energy_lab/planning/piecewise.py`
- `src/open_energy_lab/planning/optional_solver.py`

## Planned Validation Paths

- `tests/unit/tpm/`
- `tests/unit/planning/`
- `tests/unit/simulator/test_planning_export.py`
- `tests/integration/planning/`
- `tests/fixtures/planning/`
- `tests/fixtures/tpm/`

## Implemented Stable US1, US2, And US3 Surfaces

The implemented first-release public surface is:

- `open_energy_lab.simulator.PlanningExportRequest`
- `open_energy_lab.simulator.export_planning_dataset`
- `open_energy_lab.planning.PlanningDatasetArtifact`
- `open_energy_lab.planning.load_planning_dataset`
- `open_energy_lab.planning.PlanningProblemDefinition`
- `open_energy_lab.planning.PlanningProblemAssembly`
- `open_energy_lab.planning.assemble_planning_problem`
- `open_energy_lab.planning.PlanningSolveConfig`
- `open_energy_lab.planning.PlanningSolveSummary`
- `open_energy_lab.planning.PlanningSolverDependencyUnavailableError`
- `open_energy_lab.planning.PlanningSolverUnavailableError`
- `open_energy_lab.planning.solve_planning_problem`
- `open_energy_lab.tpm.TPMArtifact`
- `open_energy_lab.tpm.load_tpm_artifact`
- `open_energy_lab.tpm.TPMFeatureSpec`
- `open_energy_lab.tpm.normalize_training_data`
- `open_energy_lab.tpm.TPMFitConfig`
- `open_energy_lab.tpm.fit_tpm_artifact`
- `open_energy_lab.tpm.TPMQueryRequest`
- `open_energy_lab.tpm.query_tpm_artifact`
- `open_energy_lab.tpm.PiecewiseApproximationMetadata`
- `open_energy_lab.tpm.build_piecewise_metadata`
- `open_energy_lab.tpm.SPFlowDependencyUnavailableError`

The stable package roots remain import-light. Callers can discover the export,
planning reload, planning assembly, optional solve, and TPM entry points from
`open_energy_lab.simulator`, `open_energy_lab.planning`, and
`open_energy_lab.tpm` without importing optional SPFlow or solver stacks at
package import time.

## Committed Offline US1, US2, And US3 Fixtures

The repository now ships committed active fixtures for:

- export-request replay and expected dataset metadata in
  `tests/fixtures/planning/planning_dataset_export_case.json`
- planning-problem definition, deterministic assembly baseline, and
  optional-solve expectations in
  `tests/fixtures/planning/planning_problem_case.json`
- supported planning-dataset artifact reload in
  `tests/fixtures/tpm/planning_dataset_v1.json`
- supported TPM artifact reload in `tests/fixtures/tpm/tpm_artifact_v1.json`
- unsupported-version TPM artifact fail-fast coverage in
  `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`
- deterministic TPM query replay in `tests/fixtures/tpm/tpm_query_case.json`

These fixtures let reviewers inspect deterministic design metadata, flattened
column ordering, typed feature metadata, target semantics, artifact/query
provenance, planning-problem provenance, deterministic candidate baselines,
and version compatibility without loading any runtime `legacy/*` module. The
supported TPM artifact fixture uses a fake SPFlow backend summary, and the
planning-problem fixture uses fake-backend optional-solve expectations, so the
persisted review path stays offline and reviewable.

## Reserved Legacy Evidence Paths

- `legacy/old_tpm/src_py/simulator/data_generation.py`
- `legacy/old_tpm/src_py/simulator/feature_engineering.py`
- `legacy/old_tpm/src_py/tpm/data/datahandler.py`
- `legacy/old_tpm/src_py/tpm/data/encoding.py`
- `legacy/old_tpm/src_py/tpm/data/features/feature.py`
- `legacy/old_tpm/src_py/tpm/data/features/binary.py`
- `legacy/old_tpm/src_py/tpm/data/features/categorical.py`
- `legacy/old_tpm/src_py/tpm/data/features/contiguous.py`
- `legacy/old_tpm/src_py/tpm/data/features/mixed.py`
- `legacy/old_tpm/src_py/tpm/data/types.py`
- `legacy/old_tpm/src_py/tpm/spn/main.py`
- `legacy/old_tpm/src_py/tpm/spn/encoding.py`
- `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`
- `legacy/old_tpm/src_py/utils/densities.py`

## Preserve / Improve / Reject

### Preserve

- simulator-side ownership of family evaluation semantics and dataset export
- typed feature metadata concepts already validated in the legacy TPM code
- canonical piecewise SPN-to-planning encoding evidence where the spec names
  exact legacy paths
- import-light package roots and offline default validation

### Improve

- explicit versioned planning-dataset and TPM artifact contracts
- library-owned `shortfall` target semantics and reproducibility metadata
- stable package paths under `open_energy_lab.simulator`,
  `open_energy_lab.tpm`, and `open_energy_lab.planning`
- stable simulator-root, planning-root, and TPM-root exports for the
  implemented US1 export/reload and US2 fit/reload/query workflows
- committed deterministic fixtures for export, artifact reload, query, and
  planning assembly review

### Reject

- notebook-only dataset assembly or planning workflows
- pickle-only artifact ownership without a documented schema contract
- runtime imports from `legacy/*`
- mandatory SPFlow, Pyomo, or solver installation in the routine review path

## Phase 1 Scaffolding

Phase 1 reserved these concrete paths so later tasks could fill them with
validated behavior:

- `src/open_energy_lab/tpm/__init__.py`
- `tests/unit/tpm/__init__.py`
- `tests/unit/planning/__init__.py`
- `tests/integration/planning/__init__.py`
- `tests/fixtures/planning/README.md`
- `tests/fixtures/planning/planning_dataset_export_case.json`
- `tests/fixtures/planning/planning_problem_case.json`
- `tests/fixtures/tpm/README.md`
- `tests/fixtures/tpm/planning_dataset_v1.json`
- `tests/fixtures/tpm/tpm_artifact_v1.json`
- `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`
- `tests/fixtures/tpm/tpm_query_case.json`

These placeholders were intentionally non-runtime scaffolds. They made the
feature structure explicit before foundational tests and implementations
arrived in later phases. User Story 2 has now promoted the TPM artifact and
query fixture paths into active committed review assets.

## Phase 2 Foundational Scaffolds

Phase 2 now adds import-light module scaffolds at the reserved runtime paths:

- `src/open_energy_lab/simulator/planning_export.py`
- `src/open_energy_lab/tpm/artifact.py`
- `src/open_energy_lab/tpm/data.py`
- `src/open_energy_lab/tpm/features.py`
- `src/open_energy_lab/tpm/fit.py`
- `src/open_energy_lab/tpm/query.py`
- `src/open_energy_lab/tpm/piecewise.py`
- `src/open_energy_lab/tpm/optional_spflow.py`
- `src/open_energy_lab/planning/dataset.py`
- `src/open_energy_lab/planning/problem.py`
- `src/open_energy_lab/planning/piecewise.py`
- `src/open_energy_lab/planning/optional_solver.py`

At this stage the new modules establish:

- explicit file ownership for simulator export, TPM artifact/data/query
  handling, and planning problem assembly
- placeholder dataclasses and entry-point function names that later user-story
  tasks can implement without moving file boundaries
- lazy backend boundary helpers for SPFlow and Pyomo so package and submodule
  imports remain clear of optional research stacks until the fit or solve
  paths are invoked directly

Planning assembly modules under `open_energy_lab.planning` remain scaffolds at
this phase boundary, but the TPM modules are no longer placeholders. User
Story 2 has now promoted typed feature handling, artifact reload, fit
configuration capture, query validation, and piecewise metadata into active
reviewed behavior.

## Phase 3 User Story 1: Export Flattening And Target Semantics

`src/open_energy_lab/simulator/planning_export.py` now documents and preserves
the selected simulator export behavior with exact legacy evidence from
`legacy/old_tpm/src_py/simulator/feature_engineering.py`.

The implemented export path is:

1. Evaluate one aligned simulator family so scenario ordering, horizon length,
   timestep, and paired family seed are already fixed.
2. Build `PlanningExportRequest(...)` with one deterministic
   `scenario_index`-ordered design metadata row per scenario and one explicit
   target name (`shortfall`).
3. Call `export_planning_dataset(...)` from `open_energy_lab.simulator`.
4. Persist or inspect the returned `PlanningDatasetArtifact` directly as JSON.
5. Reload the same payload offline through
   `open_energy_lab.planning.load_planning_dataset(...)`.

The committed review path for this workflow is backed by:

- `tests/integration/planning/test_dataset_export.py`
- `tests/fixtures/planning/planning_dataset_export_case.json`
- `tests/fixtures/tpm/planning_dataset_v1.json`

### Legacy Evidence Used

- `add_aggregate_features()`
- `add_battery_panel_capacity_features()`
- `add_simple_binary_indicator()`

### Preserve

- Keep the legacy file's core intuition that simulator-produced horizon series
  are the right starting point for TPM-oriented learning inputs.
- Keep scenario-level design metadata beside those series so each exported row
  remains one design-and-weather outcome.

### Improve

- Export a stable library-owned contract with deterministic raw flattened
  columns using `<field>_<step>` names such as `ghi_0`, `load_0`, and
  `unmet_load_0`.
- Derive `shortfall` directly from simulator `unmet_load_kw`,
  `site_electric_load_kw`, and `timestep_hours` as a horizon-level energy
  ratio.
- Record this behavior in import-safe library code instead of notebook or
  dataframe-only feature-engineering steps.
- Keep the committed review payload loadable at the top level as JSON rows and
  metadata rather than introducing wrapped table payloads that need a notebook
  or dataframe tool to inspect.

### Reject

- Do not migrate the full legacy aggregate feature expansion from
  `add_aggregate_features()` into the first persisted planning-dataset
  contract.
- Do not migrate engineered blackout-label behavior from
  `add_simple_binary_indicator()`; the first planning target is the numeric
  `shortfall` ratio, not a binary failure label.
- Do not treat `legacy/old_tpm/src_py/simulator/feature_engineering.py` as a
  runtime dependency or a source of required pandas-based preprocessing.

## Implemented `shortfall` Target Semantics

The first-release target is fixed as:

`shortfall = sum(unmet_load_kw * timestep_hours) / sum(site_electric_load_kw * timestep_hours)`

This is a horizon-level electric-energy ratio, not a per-step binary label,
cooling-service adequacy score, or chance-limit parameter. The current US1
artifact metadata also pins:

- `numerator_source_field = unmet_load_kw`
- `denominator_source_field = site_electric_load_kw`
- `supported_query_mode = exceedance-probability`
- `threshold_default = 0.05`

The threshold default is recorded for downstream TPM and planning workflows,
but it is distinct from the later planning chance-limit `epsilon`. The loader
also preserves the current fail-fast rule: if total horizon load energy is
effectively zero while unmet energy is non-zero, the dataset contract is
invalid rather than silently manufacturing a ratio.

## Phase 4 User Story 2: Typed Features, Lazy SPFlow Fit, And Query Replay

`src/open_energy_lab/tpm/features.py` and `src/open_energy_lab/tpm/data.py`
now preserve the typed-feature and training-data direction from the legacy TPM
data handlers while replacing implicit state with explicit JSON-friendly
schema metadata. The current-library migration keeps continuous, binary,
categorical, and mixed feature types, stable feature ordering, explicit value
bounds, and role-aware metadata for decision, context, and target features.

### Legacy Evidence Used

- `legacy/old_tpm/src_py/tpm/data/datahandler.py`
- `legacy/old_tpm/src_py/tpm/data/features/feature.py`
- `legacy/old_tpm/src_py/tpm/data/features/binary.py`
- `legacy/old_tpm/src_py/tpm/data/features/categorical.py`
- `legacy/old_tpm/src_py/tpm/data/features/contiguous.py`
- `legacy/old_tpm/src_py/tpm/data/features/mixed.py`
- `legacy/old_tpm/src_py/tpm/data/types.py`
- `legacy/old_tpm/src_py/tpm/spn/main.py`
- `legacy/old_tpm/src_py/tpm/spn/encoding.py`
- `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`
- `legacy/old_tpm/src_py/utils/densities.py`

### Preserve

- Keep typed feature classes and role distinctions as the core TPM metadata
  shape.
- Keep stable feature ordering and explicit categorical domains because query
  validation and solver-facing encodings depend on them.
- Keep the legacy piecewise evidence path explicit in artifact metadata rather
  than hiding it in notebooks or backend-specific state.

### Improve

- Persist TPM artifacts as versioned JSON payloads that include feature
  schema, target definition, fit configuration, query configuration, and
  canonical piecewise metadata.
- Expose the TPM package through a lazy root surface so callers can import
  `open_energy_lab.tpm` without importing SPFlow.
- Capture fit outputs as a documented SPN payload representation. The current
  fixture-backed payload is a fake backend summary, which keeps offline review
  possible while documenting the contract that a real SPFlow-backed fit must
  satisfy.
- Record enough artifact provenance to reproduce the input planning dataset,
  seed lineage, and training column order.

### Reject

- Do not require runtime imports from `legacy/*` for fit, reload, or query
  flows.
- Do not widen ordinary package imports to require SPFlow.
- Do not treat pickle-only SPN ownership as the stable artifact contract.
- Do not label lower-tangent-only approximations as the canonical first
  planning-facing encoding contract.

## Implemented US2 Workflow Shape

The current stable TPM workflow is:

1. Reload the committed planning-dataset artifact through
   `open_energy_lab.planning.load_planning_dataset(...)` or provide the same
   payload directly in memory.
2. Fit a TPM artifact with `open_energy_lab.tpm.fit_tpm_artifact(...)`.
   In the default real-backend path this invokes the lazy SPFlow boundary only
   when fitting starts.
3. Persist or inspect the returned `TPMArtifact` JSON payload directly.
4. Reload the same payload offline through
   `open_energy_lab.tpm.load_tpm_artifact(...)`.
5. Evaluate a deterministic conditional probability or log-likelihood request
   with `open_energy_lab.tpm.query_tpm_artifact(...)`.

The committed review path for this workflow is backed by:

- `tests/integration/planning/test_tpm_fit_workflow.py`
- `tests/integration/planning/test_tpm_fixture_schema.py`
- `tests/fixtures/tpm/tpm_artifact_v1.json`
- `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`
- `tests/fixtures/tpm/tpm_query_case.json`

## Lazy SPFlow Boundary

SPFlow is the canonical TPM fit backend, but it remains outside import-time
package boundaries:

- importing `open_energy_lab`, `open_energy_lab.tpm`, or
  `open_energy_lab.tpm.fit` does not import SPFlow
- `open_energy_lab.tpm.require_spflow_backend()` is only invoked when
  `fit_tpm_artifact(...)` needs a real backend and the caller has not injected
  one
- unavailable-backend behavior is explicit through
  `SPFlowDependencyUnavailableError`

This keeps default review offline and import-light while still documenting the
real backend boundary clearly.

## Implemented Query Behavior

The current query surface accepts:

- one `TPMQueryRequest(...)` with explicit `decision_assignments`
- explicit `marginalized_features`
- one output mode of `conditional_probability` or `log_likelihood`
- one target name, `shortfall`

For the committed supported artifact fixture, query replay uses the empirical
planning-dataset artifact referenced by the artifact provenance. That replay
path yields:

- `matched_row_count = 1`
- `total_row_count = 2`
- `source = empirical_fixture`
- `conditional_probability = 0.0` for the committed `baseline-a` request

If no empirical dataset fixture is available, the current implementation falls
back to metadata-only behavior rather than importing SPFlow automatically.

## Phase 5 User Story 3: Planning Assembly, Optional Solve, And Unified Reproducibility

`src/open_energy_lab/planning/problem.py`,
`src/open_energy_lab/planning/piecewise.py`, and
`src/open_energy_lab/planning/optional_solver.py` now promote the first stable
planning-facing slice into the public library. The current implementation
consumes a committed TPM artifact, validates the first-release battery and
solar decision set, assembles deterministic candidate designs with canonical
piecewise metadata, and optionally hands that assembly off to a Pyomo-backed
solve boundary.

### Preserve

- Keep the first-release planning scope limited to battery and solar decision
  variables.
- Keep planning assembly offline and fixture-backed even when no real solver
  backend is installed.
- Keep the canonical piecewise planning path explicit and tied to the TPM
  artifact metadata rather than notebook-only solver glue.

### Improve

- Export planning assembly and optional solve directly from
  `open_energy_lab.planning` so the public root surface matches the shipped
  feature.
- Persist a committed planning-problem fixture with the full
  `PlanningProblemDefinition`, deterministic candidate baseline, and
  fake-backend optional-solve expectations.
- Record solver configuration, numeric tolerance, dataset fixture path, and
  deterministic baseline expectations as reproducibility metadata instead of
  leaving them implicit in test code.

### Reject

- Do not widen ordinary imports to require Pyomo or a solver binary.
- Do not broaden the first-release decision scope to inverter or other
  equipment choices.
- Do not treat solver-backed execution as required for the default review path.

## Implemented US3 Workflow Shape

The current stable planning workflow is:

1. Reload the committed TPM artifact through
   `open_energy_lab.tpm.load_tpm_artifact(...)` or provide the same artifact in
   memory.
2. Build one `PlanningProblemDefinition(...)` with explicit decision features,
   `shortfall_threshold`, `chance_limit_epsilon`, deterministic `cost_terms`,
   solver configuration, approximation contract, and fixture baseline
   expectations.
3. Assemble the deterministic offline problem through
   `open_energy_lab.planning.assemble_planning_problem(...)`.
4. Optionally solve the assembled problem through
   `open_energy_lab.planning.solve_planning_problem(...)`, either with an
   injected backend or through the lazy Pyomo boundary.
5. Inspect the returned `PlanningSolveSummary` or deterministic skip or
   infeasibility diagnostics.

The committed review path for this workflow is backed by:

- `tests/integration/planning/test_problem_assembly.py`
- `tests/integration/planning/test_optional_solve.py`
- `tests/fixtures/planning/planning_problem_case.json`

## Direct Chance-Constraint Semantics

The first-release planning adequacy rule is fixed as:

`P(shortfall > threshold) <= epsilon`

Keep these distinctions explicit:

- `threshold` is the target-event threshold for the persisted `shortfall`
  metric and defaults from the target definition to `0.05` in the committed
  fixtures.
- `epsilon` is the chance-limit bound supplied by the planning problem and is
  distinct from the target threshold itself.
- the current committed planning fixture uses `shortfall_threshold = 0.05`
  and `chance_limit_epsilon = 0.1`
- the first-release candidate baseline is deterministic: both committed
  candidate designs are feasible, and the lower-cost `baseline-a` design is
  selected with objective value `13400.0` and estimated shortfall risk `0.0`

## Lazy Pyomo Boundary

Pyomo is the canonical planning-model backend, but it remains outside
import-time package boundaries:

- importing `open_energy_lab`, `open_energy_lab.planning`, or
  `open_energy_lab.planning.problem` does not import Pyomo
- `open_energy_lab.planning.require_pyomo_backend()` is only invoked when the
  optional solve path needs the real backend and the caller has not injected
  one
- missing Pyomo surfaces as `PlanningSolverDependencyUnavailableError`
- unavailable requested solvers surface as
  `PlanningSolverUnavailableError`, or as deterministic skipped summaries when
  `skip_if_unavailable=True`

This keeps routine review import-light while still documenting the real solve
boundary and failure semantics explicitly.

## Unified Reproducibility Contract

The committed export, TPM, and planning fixtures now share one reproducibility
contract across the feature:

- the export fixture records the deterministic design rows, flattened field
  request, expected dataset id, and committed dataset artifact path
- the TPM artifact fixture records the training dataset fixture path, typed
  feature ordering, fit seed lineage, query configuration, and canonical
  piecewise metadata
- the planning fixture records the committed TPM artifact path, exact planning
  problem definition, solver configuration, deterministic candidate baseline,
  and fake-backend optional-solve expectations

Together these fixtures preserve:

- one shared feature id, `009-tpm-planning`
- explicit legacy evidence paths per workflow slice
- generation commands and refresh policies for every committed artifact
- deterministic row ordering, numeric tolerances, and solver assumptions
- a default offline review path that stays clear of mandatory SPFlow, Pyomo,
  or solver installation

## Backend-Specific Follow-Up Validation Guidance

Default review remains fixture-backed and solver-optional. Use these follow-up
checks only when the relevant backend is actually available:

- `SPFlow`: rerun the TPM fit path with the real backend to confirm the
  shipped artifact contract still matches the intended fit boundary and query
  semantics.
- `Pyomo`: rerun the planning optional-solve path with the real backend and a
  supported solver binary to confirm the shipped handoff metadata and solve
  summary match the committed fake-backend expectations closely enough for the
  selected solver environment.

If either backend is unavailable, document the skipped follow-up check rather
than widening the base environment or weakening the offline review contract.
