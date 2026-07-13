# TPM-Backed Planning Migration Note

Status: User Story 1 simulator export, persisted planning-dataset reload, and committed offline fixtures implemented

Spec `009-tpm-planning` now ships the first simulator-owned planning-dataset
export slice under `open_energy_lab.simulator`, the persisted planning-dataset
artifact contract under `open_energy_lab.planning`, and committed offline
fixtures for deterministic export replay and reload. The broader TPM fit/query
and planning assembly surfaces remain reserved for later user stories and must
still remain offline-reviewable by default.

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

## Implemented Stable US1 Surface

The implemented first-release public surface is:

- `open_energy_lab.simulator.PlanningExportRequest`
- `open_energy_lab.simulator.export_planning_dataset`
- `open_energy_lab.planning.PlanningDatasetArtifact`
- `open_energy_lab.planning.load_planning_dataset`

The stable package roots remain import-light. Callers can discover the export
and reload entry points from `open_energy_lab.simulator` and
`open_energy_lab.planning` without importing optional TPM or solver stacks.

## Committed Offline US1 Fixtures

User Story 1 now ships committed active fixtures for:

- export-request replay and expected dataset metadata in
  `tests/fixtures/planning/planning_dataset_export_case.json`
- supported planning-dataset artifact reload in
  `tests/fixtures/tpm/planning_dataset_v1.json`

These fixtures let reviewers inspect deterministic design metadata, flattened
column ordering, target semantics, and provenance without refitting a TPM,
running a solver, or loading any runtime `legacy/*` module.

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
- stable simulator-root and planning-root exports for the implemented US1
  export and reload workflow
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
arrived in later phases.

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

These Phase 2 modules are still scaffolds. They intentionally reserve the
runtime and documentation surface without claiming that dataset export, TPM
artifact reload, backend-backed querying, or planning-model solve behavior is
already implemented.

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
